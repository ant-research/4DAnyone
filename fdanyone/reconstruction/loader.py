"""Prefetch input batches without advancing the checkpoint's committed sampler."""

import cv2
import torch
from torch.utils.data import DataLoader, Dataset


class Sampler:
    def __init__(self, size, seed):
        self.size = size
        self.generator = torch.Generator().manual_seed(seed)
        self.order = torch.empty(0, dtype=torch.long)
        self.position = 0

    def next(self, count, step):
        # The established recipe opens a new 500-iteration loader each epoch.
        if step % 500 == 0 or self.position >= len(self.order):
            self.order = torch.randperm(self.size, generator=self.generator)
            self.position = 0
        result = self.order[self.position : self.position + count].tolist()
        self.position += len(result)
        return result

    def state_dict(self):
        return dict(order=self.order, position=self.position, rng=self.generator.get_state())

    def restore(self, state):
        self.order, self.position = state["order"].cpu(), state["position"]
        self.generator.set_state(state["rng"].cpu())


class InputPixels(Dataset):
    def __init__(self, training_data):
        self.training_data = training_data

    def __getitem__(self, index):
        return torch.from_numpy(self.training_data.pixels(index)), index

    def __len__(self):
        return len(self.training_data)


def worker_init(worker_id):
    cv2.setNumThreads(1)
    torch.set_num_threads(1)


def planned_batches(sampler, count, start, end):
    for step in range(start, end):
        yield sampler.next(count, step)


def batches(training_data, sampler, start, end, device, *, batch_size, loader_workers, seed):
    # DataLoader may request several future batches. Only the consumer commits progress.
    planned = Sampler(sampler.size, seed)
    planned.restore(sampler.state_dict())
    kwargs = dict(prefetch_factor=2, multiprocessing_context="spawn") if loader_workers else {}
    loader = DataLoader(
        InputPixels(training_data),
        batch_sampler=planned_batches(planned, batch_size, start, end),
        num_workers=loader_workers,
        pin_memory=True,
        worker_init_fn=worker_init,
        generator=torch.Generator().manual_seed(seed),
        **kwargs,
    )
    iterator = iter(loader)
    stream = torch.cuda.Stream(device=device)

    def preload():
        try:
            pixels, indices = next(iterator)
        except StopIteration:
            return None
        with torch.cuda.stream(stream):
            pixels = pixels.to(device, non_blocking=True).float().div_(255)
        return pixels, indices.tolist()

    pending = preload()
    for step in range(start, end):
        torch.cuda.current_stream(device).wait_stream(stream)
        pixels, indices = pending
        pixels.record_stream(torch.cuda.current_stream(device))
        pending = preload() if step + 1 < end else None
        expected = sampler.next(batch_size, step)
        if indices != expected:
            raise RuntimeError("Prefetched batch differs from committed sampler")
        yield pixels, indices
