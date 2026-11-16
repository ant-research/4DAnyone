"""Single-owner playback with one image awaiting browser presentation at a time."""

import asyncio
import json
import math
import struct
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from urllib.parse import urlsplit

import anyio
from starlette.applications import Starlette
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Mount, Route, WebSocketRoute
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocketDisconnect

from .camera import orbit_camera


def integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"Expected an integer in [{low}, {high}]")
    return value


def viewport_resolution(viewport, native_height):
    width = integer(viewport["width"], 1, 16384)
    height = integer(viewport["height"], 1, 16384)
    aspect = width / height
    # Preserve native vertical sampling; expand the horizontal field of view.
    out_height = float(native_height)
    out_width = out_height * aspect
    scale = min(1.0, 8192 / max(out_width, out_height), math.sqrt(8_388_608 / (out_width * out_height)))
    return max(1, math.floor(out_width * scale)), max(1, math.floor(out_height * scale))


def validate_request(data, frames, render_width, render_height, *, fit_viewport=False):
    seq = integer(data["seq"], 0, 2**53 - 1)
    epoch = integer(data["epoch"], 0, 2**53 - 1)
    frame = integer(data["frame"], 0, frames - 1)
    quality, background = data["quality"], data["background"]
    if quality not in ("final", "lossless") or background not in ("black", "gray", "white"):
        raise ValueError("Invalid quality or background")
    layers = data.get("layers", False)
    if type(layers) is not bool:
        raise ValueError("Invalid compositor capability")
    if fit_viewport:
        viewport = data.get("viewport", dict(width=render_width, height=render_height))
        render_width, render_height = viewport_resolution(viewport, render_height)
    camera = orbit_camera(data["camera"], render_width, render_height)
    return dict(seq=seq, epoch=epoch, frame=frame, camera=camera, quality=quality, background=background, layers=layers)


class Session:
    def __init__(self):
        self.pending = None
        self.changed = asyncio.Event()
        self.ack = asyncio.Event()
        self.awaiting = None
        self.last_seq = -1

    def submit(self, request):
        if request["seq"] <= self.last_seq:
            raise ValueError("Request sequence must increase")
        self.last_seq = request["seq"]
        self.pending = request
        self.changed.set()

    def acknowledge(self, seq):
        if type(seq) is int and seq == self.awaiting:
            self.ack.set()


def create_app(
    model=None,
    *,
    device="cuda",
    title=None,
    width=None,
    height=None,
    max_fps=30,
    ground_grid=True,
    renderer_factory=None,
):
    if (width is None) != (height is None):
        raise ValueError("Specify both width and height, or use the original checkpoint resolution")
    if width is not None:
        integer(width, 64, 8192)
        integer(height, 64, 8192)
    if not math.isfinite(max_fps) or not 1 <= max_fps <= 60:
        raise ValueError("max_fps must be between 1 and 60")
    assets = Path(__file__).with_name("assets")
    fonts = Path(__file__).parents[2] / "space/assets"
    gpu = ThreadPoolExecutor(max_workers=1, thread_name_prefix="4dgs-render")
    encoder = ThreadPoolExecutor(max_workers=1, thread_name_prefix="4dgs-encode")
    owner = None
    renderer = None

    def initialize():
        nonlocal renderer
        if renderer_factory is not None:
            renderer = renderer_factory()
        else:
            from .renderer import Renderer

            renderer = Renderer(model, device, title, ground_grid=ground_grid)
        renderer.metadata["render_width"] = integer(width or renderer.metadata["width"], 1, 8192)
        renderer.metadata["render_height"] = integer(height or renderer.metadata["height"], 1, 8192)
        renderer.metadata["render_mode"] = "viewport" if width is None else "fixed"
        warm = dict(camera=orbit_camera(renderer.metadata["camera"], 128, 128), frame=0, background="black")
        renderer.image(warm)

    @asynccontextmanager
    async def lifespan(app):
        try:
            await asyncio.get_running_loop().run_in_executor(gpu, initialize)
            yield
        finally:
            gpu.shutdown(wait=True, cancel_futures=True)
            encoder.shutdown(wait=True, cancel_futures=True)

    async def index(request):
        return FileResponse(assets / "index.html", headers={"Cache-Control": "no-cache"})

    async def font(request):
        name = request.path_params["name"]
        if name not in ("lato-latin-400-normal.woff2", "lato-latin-700-normal.woff2"):
            return JSONResponse({"error": "not found"}, status_code=404)
        return FileResponse(fonts / name, media_type="font/woff2")

    async def health(request):
        return JSONResponse({"ready": renderer is not None, "busy": owner is not None})

    async def socket(ws):
        nonlocal owner
        origin = ws.headers.get("origin")
        if origin and urlsplit(origin).netloc.lower() != ws.headers.get("host", "").lower():
            await ws.close(code=1008)
            return
        await ws.accept()
        if owner is not None:
            await ws.send_json(dict(type="busy", message="This viewer is in use. Close the other tab, then reconnect."))
            await ws.close(code=1013)
            return
        session = Session()
        owner = session
        task = receiving = None
        loop = asyncio.get_running_loop()

        async def receive():
            while True:
                text = (
                    await ws.receive_text()
                )  # Uvicorn protocol ping/pong detects dead connections, including idle tabs.
                if len(text) > 16384:
                    raise ValueError("Message is too large")
                data = json.loads(text)
                if data["type"] == "view":
                    request = validate_request(
                        data,
                        renderer.metadata["frames"],
                        renderer.metadata["render_width"],
                        renderer.metadata["render_height"],
                        fit_viewport=width is None,
                    )
                    session.submit(request)
                elif data["type"] == "ack":
                    session.acknowledge(data.get("seq"))
                elif data["type"] != "ping":
                    raise ValueError("Unknown message type")

        async def produce():
            from .renderer import encode_frame

            last = 0
            while True:
                await session.changed.wait()
                await asyncio.sleep(max(0, 1 / max_fps - (time.perf_counter() - last)))
                request, session.pending = session.pending, None
                session.changed.clear()
                last = time.perf_counter()
                pixels, stats = await loop.run_in_executor(gpu, renderer.image, request)
                # A completed camera frame is useful while dragging. Old seek epochs are not.
                if session.pending and session.pending["epoch"] != request["epoch"]:
                    continue
                image, encode_ms, descriptor = await loop.run_in_executor(
                    encoder, encode_frame, pixels, request["quality"]
                )
                header = dict(
                    type="frame",
                    seq=request["seq"],
                    epoch=request["epoch"],
                    frame=request["frame"],
                    quality=request["quality"],
                    width=pixels.shape[1],
                    height=pixels.shape[0],
                    encode_ms=encode_ms,
                    **descriptor,
                    **stats,
                )
                encoded = json.dumps(header, allow_nan=False).encode()
                session.ack.clear()
                session.awaiting = request["seq"]
                await asyncio.wait_for(ws.send_bytes(struct.pack("!I", len(encoded)) + encoded + image), timeout=10)
                # ACK is sent only after decode and canvas paint (or explicit stale-frame discard).
                await asyncio.wait_for(session.ack.wait(), timeout=10)

        async def report_error(message):
            with suppress(RuntimeError, WebSocketDisconnect, TimeoutError):
                await asyncio.wait_for(ws.send_json(dict(type="error", message=message)), timeout=1)

        try:
            await ws.send_json(dict(type="hello", max_fps=max_fps, **renderer.metadata))
            task = asyncio.create_task(produce())
            receiving = asyncio.create_task(receive())
            done, _ = await asyncio.wait((task, receiving), return_when=asyncio.FIRST_COMPLETED)
            for completed in done:
                completed.result()
        except WebSocketDisconnect:
            pass
        except (ValueError, KeyError, TypeError, TimeoutError) as exc:
            await report_error(f"Connection ended: {type(exc).__name__}. Please reconnect.")
        except Exception:
            import logging

            logging.exception("4DGS rendering failed")
            await report_error("Rendering failed. See the server log, then reconnect.")
        finally:
            # Release synchronously: ASGI cancellation may interrupt any cleanup await.
            if owner is session:
                owner = None
            running = [job for job in (task, receiving) if job is not None]
            for job in running:
                job.cancel()
            # Do not let ASGI level-cancellation interrupt child-task cleanup.
            with anyio.CancelScope(shield=True):
                await asyncio.gather(*running, return_exceptions=True)
                with suppress(RuntimeError, WebSocketDisconnect, TimeoutError):
                    await asyncio.wait_for(ws.close(), timeout=2)

    return Starlette(
        lifespan=lifespan,
        routes=[
            Route("/", index),
            Route("/health", health),
            Route("/fonts/{name}", font),
            WebSocketRoute("/ws", socket),
            Mount("/assets", app=StaticFiles(directory=assets)),
        ],
    )
