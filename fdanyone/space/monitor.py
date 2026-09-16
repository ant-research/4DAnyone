"""Bounded console output and two-stage progress from the ordinary CLI run."""

from __future__ import annotations

import codecs
import re
from collections import deque
from pathlib import Path

MAX_LOG_BYTES = 64 * 1024
MAX_READ_BYTES = 128 * 1024
MAX_LOG_LINES = 500
ANSI = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))")
COUNTER = re.compile(r"^([^:]+):\s*\d+%.*?\|\s*(\d+)/(\d+)\s+\[")
DISTRIBUTED_STEP = re.compile(r"Completed target denoising step (\d+)/(\d+)")


class ConsoleTail:
    """Read appended bytes, retaining terminal carriage-return behavior."""

    def __init__(self):
        self.offset = 0
        self.identity = None
        self.lines = deque(maxlen=MAX_LOG_LINES)
        self.line = ""
        self.escape = ""
        self.decoder = codecs.getincrementaldecoder("utf-8")("replace")

    def read(self, path: Path, observe=lambda line: None) -> str:
        try:
            stat = path.stat()
            identity = (stat.st_dev, stat.st_ino)
            if self.identity != identity or stat.st_size < self.offset:
                self.__init__()
                self.identity = identity
            if stat.st_size == self.offset:
                return self.text
            with path.open("rb") as stream:
                if stat.st_size - self.offset > MAX_READ_BYTES:
                    # A browser joining a long run needs the latest output.
                    self.offset = max(0, stat.st_size - MAX_READ_BYTES)
                    self.lines.clear()
                    self.line = self.escape = ""
                    self.decoder.reset()
                    stream.seek(self.offset)
                else:
                    stream.seek(self.offset)
                chunk = stream.read(MAX_READ_BYTES)
                self.offset = stream.tell()
        except FileNotFoundError:
            return self.text
        text = self.escape + self.decoder.decode(chunk)
        self.escape = ""
        last_escape = text.rfind("\x1b")
        if last_escape >= 0 and not ANSI.fullmatch(text[last_escape:]) and not ANSI.match(text[last_escape:]):
            self.escape, text = text[last_escape:][-256:], text[:last_escape]
        for fragment in re.split(r"([\r\n\b])", ANSI.sub("", text)):
            if fragment in {"\r", "\n"}:
                observe(self.line)
                if fragment == "\n":
                    self.lines.append(self.line)
                self.line = ""
            elif fragment == "\b":
                self.line = self.line[:-1]
            else:
                fragment = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", fragment)
                self.line = (self.line + fragment)[-MAX_LOG_BYTES:]
        observe(self.line)
        # Bound server memory as well as each browser update.
        size = len(self.line)
        for line in reversed(self.lines):
            size += len(line) + 1
        while self.lines and size > MAX_LOG_BYTES:
            size -= len(self.lines.popleft()) + 1
        return self.text

    @property
    def text(self) -> str:
        return "\n".join([*self.lines, self.line]).rstrip("\n")[-MAX_LOG_BYTES:]


class RunMonitor:
    """Progress advances on stage events and completed work, never on a timer.

    Segment positions represent pipeline milestones, not elapsed-time estimates.
    Actual frame/batch/denoising counters are shown in the accompanying detail.
    Unknown-duration preparation and saving retain their milestone position.
    """

    def __init__(self):
        self.console = ConsoleTail()
        self.stage = 0
        self.progress = [0.0, 0.0]
        self.detail = "Preparing Inference"
        self.last_status = None

    def advance(self, stage: int, fraction: float, detail: str):
        if stage < self.stage or fraction < self.progress[stage]:
            return
        self.stage = stage
        if stage == 1:
            self.progress[0] = 1.0
        self.progress[stage] = min(fraction, 0.99)
        self.detail = detail

    def status(self, status: dict):
        identity = (status.get("fraction"), status.get("message"), status.get("error"))
        if identity == self.last_status or status.get("error"):
            return
        self.last_status = identity
        fraction = float(status.get("fraction", 0))
        if fraction >= 1:
            self.advance(1, 0.97, "Finishing Inference")
        elif fraction >= 0.92:
            self.advance(1, 0.94, "Validating Videos")
        elif fraction >= 0.45:
            self.advance(1, 0.15, "Loading Models And Encoding Input")
        elif fraction >= 0.30:
            self.advance(1, 0.03, "Preparing Masks And Skeletons")
        elif fraction >= 0.15:
            self.advance(0, 0.15, "Recovering 3D Motion")
        elif fraction >= 0.10:
            self.advance(0, 0.10, "Preparing Input Clip")
        elif fraction >= 0.05:
            self.advance(0, 0.04, "Preparing Model Assets")
        else:
            self.advance(0, 0.01, "Checking Input And Settings")

    def observe(self, line: str):
        if match := COUNTER.search(line.strip()):
            label, done, total = match.groups()
            done, total = int(done), int(total)
            if total <= 0 or done > total:
                return
            part = done / total
            if label == "YoloV8 Tracking":
                self.advance(0, 0.15 + 0.40 * part, f"Tracking Person · {done}/{total} Frames")
            elif label == "ViTPose":
                self.advance(0, 0.55 + 0.15 * part, f"Estimating Pose · {done}/{total} Batches")
            elif label == "HMR2 Feature":
                self.advance(0, 0.70 + 0.15 * part, f"Extracting Features · {done}/{total} Batches")
            elif label.startswith("RCP 1-to-"):
                self.advance(1, 0.20 + 0.15 * part, f"Reference Views · Step {done}/{total}")
            elif re.fullmatch(r"Generate \d+ target views", label):
                self.advance(1, 0.40 + 0.45 * part, f"Target Views · Step {done}/{total}")
        elif match := DISTRIBUTED_STEP.search(line):
            done, total = map(int, match.groups())
            if total > 0 and done <= total:
                self.advance(1, 0.40 + 0.45 * done / total, f"Target Views · Step {done}/{total}")
        elif "[Preprocess] End." in line:
            self.advance(0, 0.88, "Recovering 3D Motion")
        elif "Reusing GVHMR motion from " in line:
            self.advance(0, 0.95, "Reusing Recovered Motion")
        elif "Publishing target camera " in line:
            self.advance(1, 0.90, "Encoding And Saving Videos")

    def payload(self, *, token, name, state, message, elapsed, log_path=None, stopping=False) -> dict:
        if log_path is not None:
            self.console.read(log_path, self.observe)
        stage, progress, detail = self.stage, list(self.progress), self.detail
        if state == "queued":
            detail = "Preparing Inference"
        elif state == "complete":
            stage, progress, detail = 1, [1.0, 1.0], "Complete"
        elif state == "failed":
            detail = message
        elif state == "cancelled":
            detail = "Stopped · Saved Results Are Kept"
        if stopping and state not in {"complete", "failed", "cancelled"}:
            detail = "Stopping Inference"
        return {
            "token": token,
            "name": name,
            "state": state,
            "stage": stage,
            "progress": progress,
            "detail": detail,
            "elapsed": elapsed,
            "log": self.console.text,
        }


def preparing_monitor() -> dict:
    return RunMonitor().payload(token="preparing", name="", state="starting", message="", elapsed=None)


MONITOR_HTML = """
<section class="run-monitor" aria-label="Inference Progress" hidden>
  <div class="run-stages">
    <div class="run-stage" data-stage="0">
      <div class="stage-label"><span class="stage-icon">1</span>Recovering Motion</div>
      <div class="stage-track" role="progressbar" aria-label="Recovering Motion" aria-valuemin="0" aria-valuemax="100">
        <div class="stage-fill"></div>
      </div>
    </div>
    <div class="run-stage" data-stage="1">
      <div class="stage-label"><span class="stage-icon">2</span>Generating Videos</div>
      <div class="stage-track" role="progressbar" aria-label="Generating Videos" aria-valuemin="0" aria-valuemax="100">
        <div class="stage-fill"></div>
      </div>
    </div>
  </div>
  <div class="run-detail"><span class="run-step" role="status"></span><span class="run-elapsed"></span></div>
  <section class="run-console" aria-label="Console">
    <div class="console-heading">
      <button type="button" class="console-toggle" aria-expanded="true">Console <span>▾</span></button>
      <span class="console-run"></span>
      <button type="button" class="console-follow" hidden>Follow</button>
    </div>
    <pre class="console-log" tabindex="0" aria-label="Inference Console" aria-live="off"></pre>
  </section>
</section>
"""

MONITOR_JS = Path(__file__).with_name("assets").joinpath("monitor.js").read_text()
