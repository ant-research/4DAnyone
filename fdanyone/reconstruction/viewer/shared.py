"""Local leases and process startup for viewers sharing one public port (Linux)."""

import contextlib
import errno
import json
import os
import re
import socket
import stat
import subprocess
import sys
import time
from pathlib import Path

from fdanyone.errors import ConfigurationError

PROTOCOL = 1
WS_OPTIONS = dict(
    ws="websockets",
    ws_max_size=16384,
    ws_max_queue=1,
    ws_ping_interval=5,
    ws_ping_timeout=10,
    ws_per_message_deflate=False,
)


def validate_label(label):
    if not isinstance(label, str) or (label and not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,31}", label)):
        raise ConfigurationError("label must be empty or 1–32 lowercase letters, digits, hyphens or underscores")
    return label


def runtime_directory():
    if sys.platform != "linux":
        raise ConfigurationError("Shared-port viewers require Linux")
    base = Path(os.environ.get("XDG_RUNTIME_DIR") or "/tmp")
    path = base / f"4danyone-viewer-{os.getuid()}"
    # Leave room for the longest generated socket filename and its NUL terminator.
    if len(os.fsencode(path)) + 40 >= 108:
        path = Path("/tmp") / f"4danyone-viewer-{os.getuid()}"
    path.mkdir(mode=0o700, exist_ok=True)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise ConfigurationError(
            f"Viewer runtime directory must be owned by you, private (0700), and not a symlink: {path}"
        )
    return path


def endpoint(host, port):
    if not isinstance(host, str) or not host:
        raise ConfigurationError("host must be a nonempty hostname or IP address")
    if type(port) is not int or not 1 <= port <= 65535:
        raise ConfigurationError("port must be an integer from 1 to 65535")
    try:
        addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM, flags=socket.AI_PASSIVE)
    except (OSError, TypeError) as exc:
        raise ConfigurationError(f"Invalid host: {host}") from exc
    family, _, _, _, address = addresses[0]
    return family, address


def url(host, port, label):
    host = "127.0.0.1" if host == "0.0.0.0" else "::1" if host == "::" else host
    return f"http://{'[' + host + ']' if ':' in host else host}:{port}/{label}/"


def receive(sock):
    data = bytearray()
    while len(data) <= 8192:
        chunk = sock.recv(1)
        if not chunk:
            raise ConnectionResetError("Viewer gateway disconnected during registration")
        if chunk == b"\n":
            return json.loads(data)
        data.extend(chunk)
    raise ConfigurationError("Invalid viewer gateway response")


def connect(path):
    sock = socket.socket(socket.AF_UNIX)
    try:
        sock.settimeout(15)
        sock.connect(str(path))
        return sock
    except BaseException:
        sock.close()
        raise


def start_gateway(directory, host, port, family, address):
    listener = socket.socket(family)
    try:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(address)
        listener.listen(128)
        with (directory / f"gateway-{port}.log").open("ab") as log:
            return subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "fdanyone.reconstruction.viewer.gateway",
                    str(directory),
                    host,
                    str(port),
                    str(listener.fileno()),
                ],
                cwd=Path(__file__).resolve().parents[3],
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=log,
                pass_fds=(listener.fileno(),),
                start_new_session=True,
            )
    finally:
        listener.close()


def register(host, port, label, *, title=None):
    """Reserve a label before importing a renderer or loading its checkpoint."""
    validate_label(label)
    family, address = endpoint(host, port)
    directory = runtime_directory()
    import fcntl

    control = directory / f"control-{port}.sock"
    # Serialize startup across CLI invocations. No GPU or HTTP work happens under this lock.
    with (directory / f"start-{port}.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        deadline = time.monotonic() + 15
        process, restarting = None, False
        while time.monotonic() < deadline:
            sock = None
            try:
                try:
                    sock = connect(control)
                except (FileNotFoundError, ConnectionRefusedError):
                    if process is None:
                        try:
                            process = start_gateway(directory, host, port, family, address)
                        except OSError as exc:
                            if exc.errno != errno.EADDRINUSE:
                                raise
                            if not restarting:
                                raise ConfigurationError(
                                    f"Port {port} is occupied by another service (possibly app.py). "
                                    "Choose a different --port."
                                ) from exc
                    elif process.poll() is not None:
                        raise ConfigurationError(
                            f"Viewer gateway failed to start; see {directory / f'gateway-{port}.log'}"
                        ) from None
                if sock is not None:
                    sock.settimeout(max(0.01, deadline - time.monotonic()))
                    sock.sendall(
                        json.dumps(dict(protocol=PROTOCOL, host=host, label=label, title=title)).encode() + b"\n"
                    )
                    result = receive(sock)
                    if "error" in result:
                        if result.get("retry"):
                            raise ConnectionResetError(result["error"])
                        raise ConfigurationError(result["error"])
                    if result.get("protocol") != PROTOCOL or Path(result["socket"]).parent != directory:
                        raise ConfigurationError("Incompatible viewer gateway; stop its viewers before retrying")
                    sock.settimeout(None)
                    lease, sock = sock, None
                    return lease, result
            except (ConnectionError, TimeoutError):
                # Idle shutdown can race with connect, accept, or the registration reply.
                restarting = True
            finally:
                if sock is not None:
                    sock.close()
            time.sleep(0.05)
        if process is not None and process.poll() is None:
            process.terminate()
            process.wait(timeout=5)
        raise ConfigurationError(f"Viewer gateway did not become ready; see {directory / f'gateway-{port}.log'}")


async def run_worker(app, sock, registration, host, port):
    import asyncio

    import uvicorn

    path = Path(registration["socket"])
    sock.setblocking(False)
    reader, writer = await asyncio.open_connection(sock=sock)
    config = uvicorn.Config(app, uds=str(path), log_level="warning", timeout_graceful_shutdown=3, **WS_OPTIONS)
    server = uvicorn.Server(config)

    async def announce():
        while not server.started:
            await asyncio.sleep(0.02)
        writer.write(b'{"ready":true}\n')
        await writer.drain()
        response = await reader.readline()
        if not response or not json.loads(response).get("ready"):
            raise ConfigurationError("Viewer gateway disconnected before the scene became ready")
        print(f"Viewing {url(host, port, registration['label'])} (Ctrl+C removes this scene)", flush=True)
        await reader.read(1)
        raise ConfigurationError("Viewer gateway stopped")

    serving = asyncio.create_task(server.serve())
    announcing = asyncio.create_task(announce())
    try:
        done, _ = await asyncio.wait((serving, announcing), return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
    finally:
        writer.close()
        announcing.cancel()
        server.should_exit = True
        await asyncio.gather(announcing, return_exceptions=True)
        await serving
        with contextlib.suppress(FileNotFoundError):
            path.unlink()


def view(
    model,
    *,
    label="",
    host="127.0.0.1",
    port=7861,
    device="cuda",
    title=None,
    width=None,
    height=None,
    max_fps=30,
    ground_grid=True,
):
    """View an NPZ at /<label>/. Empty label generates a random name.

    Repeated commands share the port; Ctrl+C removes only this command's scene.
    Relative model paths use the code repository root.
    """
    import asyncio

    model = (Path(__file__).resolve().parents[3] / Path(model).expanduser()).resolve()
    if not model.is_file():
        raise ConfigurationError(f"Checkpoint not found: {model}")
    title = title or (model.parent.parent.name if model.parent.name == "checkpoints" else model.stem)
    sock, registration = register(host, port, label, title=title)
    try:
        from .server import create_app

        app = create_app(
            model, device=device, title=title, width=width, height=height, max_fps=max_fps, ground_grid=ground_grid
        )
        with contextlib.suppress(KeyboardInterrupt):
            asyncio.run(run_worker(app, sock, registration, host, port))
    finally:
        sock.close()
