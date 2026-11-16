"""GPU-free gateway; private Unix connections own the registered scene routes."""

import asyncio
import html
import json
import os
import secrets
import socket
import sys
import time
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import uvicorn
from starlette.applications import Starlette
from starlette.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.routing import Mount, Route, WebSocketRoute
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocketDisconnect
from websockets.asyncio.client import unix_connect
from websockets.exceptions import ConnectionClosed, InvalidHandshake

from fdanyone.errors import ConfigurationError

from .shared import PROTOCOL, WS_OPTIONS, validate_label


@dataclass
class Scene:
    label: str
    path: Path
    title: str = ""
    ready: bool = False
    connections: set = field(default_factory=set)


class Gateway:
    def __init__(self, directory, host, port, *, idle_seconds=20):
        self.directory, self.host, self.port = Path(directory), host, port
        self.control = self.directory / f"control-{port}.sock"
        self.scenes = {}
        self.clients = set()
        self.empty_since = time.monotonic()
        self.idle_seconds = idle_seconds
        self.server = None
        self.closing = False

    async def register(self, reader, writer):
        task = asyncio.current_task()
        self.clients.add(task)
        scene = None
        try:
            if self.closing:
                raise ConfigurationError("Viewer gateway is stopping")
            message = json.loads(await asyncio.wait_for(reader.readline(), timeout=10))
            if self.closing:
                raise ConfigurationError("Viewer gateway is stopping")
            if message.get("protocol") != PROTOCOL:
                raise ConfigurationError("Incompatible viewer gateway; stop its viewers before retrying")
            if message.get("host") != self.host:
                raise ConfigurationError(f"This port's viewers use --host {self.host}; use the same host")
            label = validate_label(message.get("label", ""))
            if label and label in self.scenes:
                raise ConfigurationError(f"Viewer label '{label}' is already in use")
            while not label or label in self.scenes:
                label = secrets.token_hex(4)
            title = message.get("title") or label
            if not isinstance(title, str) or len(title) > 200:
                raise ConfigurationError("Scene title must be at most 200 characters")
            scene = Scene(label, self.directory / f"worker-{secrets.token_hex(8)}.sock", title=title)
            self.scenes[label] = scene
            writer.write(
                json.dumps(dict(protocol=PROTOCOL, label=label, socket=str(scene.path), pid=os.getpid())).encode()
                + b"\n"
            )
            await writer.drain()
            ready = await reader.readline()
            if not ready:
                return
            if json.loads(ready) != {"ready": True}:
                raise ConfigurationError("Invalid viewer readiness message")
            scene.ready = True
            writer.write(b'{"ready":true}\n')
            await writer.drain()
            await reader.read(1)  # The connection is the lease, including SIGKILL cleanup.
        except (ConfigurationError, ValueError, TypeError, AttributeError, TimeoutError) as exc:
            with suppress(OSError):
                writer.write(json.dumps(dict(error=str(exc), retry=self.closing)).encode() + b"\n")
                await writer.drain()
        except (ConnectionError, asyncio.IncompleteReadError):
            pass
        finally:
            if scene is not None:
                self.scenes.pop(scene.label, None)
                connections = tuple(scene.connections)
                for connection in connections:
                    connection.cancel()
                await asyncio.gather(*connections, return_exceptions=True)
                with suppress(FileNotFoundError):
                    scene.path.unlink()
            writer.close()
            with suppress(ConnectionError):
                await writer.wait_closed()
            self.clients.discard(task)
            self.empty_since = time.monotonic()

    async def idle(self):
        while True:
            await asyncio.sleep(0.25)
            if not self.clients and time.monotonic() - self.empty_since >= self.idle_seconds:
                self.closing = True
                self.server.should_exit = True
                return

    @asynccontextmanager
    async def lifespan(self, app):
        # Only a process holding the public TCP socket may replace a stale control socket.
        with suppress(FileNotFoundError):
            self.control.unlink()
        control = await asyncio.start_unix_server(self.register, path=str(self.control), limit=8192)
        identity = self.control.lstat()
        idle = asyncio.create_task(self.idle())
        try:
            yield
        finally:
            self.closing = True
            control.close()
            idle.cancel()
            clients = tuple(self.clients)
            for client in clients:
                client.cancel()
            await asyncio.gather(idle, *clients, return_exceptions=True)
            # Python 3.12+ also waits for accepted connections: close the leases first.
            await control.wait_closed()
            with suppress(FileNotFoundError):
                current = self.control.lstat()
                if (current.st_dev, current.st_ino) == (identity.st_dev, identity.st_ino):
                    self.control.unlink()

    async def index(self, request):
        rows = []
        for scene in self.scenes.values():
            title = f'<span class="scene-title">{html.escape(scene.title or scene.label)}</span>'
            if scene.ready:
                row = (
                    f'<a class="scene-card" href="{scene.label}/">{title}'
                    '<span class="scene-action">Open scene <span aria-hidden="true">↗</span></span></a>'
                )
            else:
                row = (
                    f'<div class="scene-card" aria-disabled="true">{title}'
                    '<span class="scene-action">Loading…</span></div>'
                )
            rows.append(f"<li>{row}</li>")
        content = (
            '<ul class="scene-list">' + "".join(rows) + "</ul>"
            if rows
            else '<div class="scene-empty"><p>No scenes are open.</p>'
            "<p>Refresh this page after opening a scene.</p></div>"
        )
        return HTMLResponse(
            '<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            "<title>4DGS scenes · 4DAnyone</title>"
            '<link rel="stylesheet" href="_ui/assets/scenes.css"></head><body>'
            '<main class="scenes"><header class="scene-header">'
            '<span class="viewer-brand">4DAnyone</span>'
            '<a class="scene-refresh" href="./">Refresh</a></header>'
            '<div class="scene-heading"><div><h1>4DGS scenes</h1>'
            "<p>Choose a scene to explore.</p></div>"
            f'<span class="scene-count">{len(rows)} {"scene" if len(rows) == 1 else "scenes"}</span></div>'
            + content
            + "</main></body></html>",
            headers={"Cache-Control": "no-store"},
        )

    async def font(self, request):
        name = request.path_params["name"]
        if name not in ("lato-latin-400-normal.woff2", "lato-latin-700-normal.woff2"):
            return Response(status_code=404)
        return FileResponse(Path(__file__).parents[2] / "space/assets" / name, media_type="font/woff2")

    async def redirect(self, request):
        # A relative redirect also works when a reverse proxy adds a URL prefix.
        return RedirectResponse(
            request.url.path.rsplit("/", 1)[-1] + "/" + ("?" + request.url.query if request.url.query else "")
        )

    async def http(self, request):
        scene = self.scenes.get(request.path_params["label"])
        if scene is None:
            return JSONResponse({"error": "Scene not found"}, status_code=404)
        if not scene.ready:
            return JSONResponse({"error": "Scene is loading"}, status_code=503)
        path = "/" + request.path_params.get("path", "")
        headers = {"host": request.headers["host"], "accept-encoding": "identity"}
        for name in ("if-none-match", "if-modified-since", "range"):
            if name in request.headers:
                headers[name] = request.headers[name]
        try:
            async with httpx.AsyncClient(transport=httpx.AsyncHTTPTransport(uds=str(scene.path))) as client:
                response = await client.request(
                    request.method,
                    "http://viewer" + path,
                    params=request.query_params,
                    headers=headers,
                    timeout=10,
                )
            headers = dict(response.headers)
            for name in ("connection", "transfer-encoding"):
                headers.pop(name, None)
            if "location" in headers:
                location = urlsplit(headers["location"])
                headers["location"] = f"/{scene.label}{location.path}" + (
                    "?" + location.query if location.query else ""
                )
            return Response(response.content, status_code=response.status_code, headers=headers)
        except httpx.HTTPError:
            return JSONResponse({"error": "Scene is unavailable"}, status_code=503)

    async def websocket(self, ws):
        scene = self.scenes.get(ws.path_params["label"])
        origin, host = ws.headers.get("origin"), ws.headers.get("host", "")
        if origin and urlsplit(origin).netloc.lower() != host.lower():
            await ws.close(code=1008)
            return
        if scene is None or not scene.ready:
            await ws.close(code=1008)
            return
        current = asyncio.current_task()
        scene.connections.add(current)
        jobs = []
        code, reason = 1000, ""
        try:
            async with unix_connect(
                str(scene.path),
                uri=f"ws://{host}/ws",
                origin=origin,
                max_size=64 * 1024**2,
                max_queue=1,
                compression=None,
                ping_interval=5,
                ping_timeout=10,
                open_timeout=10,
                close_timeout=2,
            ) as backend:
                await ws.accept()

                async def upstream():
                    while True:
                        message = await ws.receive()
                        if message["type"] == "websocket.disconnect":
                            return
                        await backend.send(
                            message.get("bytes") if message.get("bytes") is not None else message["text"]
                        )

                async def downstream():
                    async for message in backend:
                        if isinstance(message, bytes):
                            await ws.send_bytes(message)
                        else:
                            await ws.send_text(message)

                jobs = [asyncio.create_task(upstream()), asyncio.create_task(downstream())]
                done, _ = await asyncio.wait(jobs, return_when=asyncio.FIRST_COMPLETED)
                for job in done:
                    job.result()
                code = backend.close_code or 1000
        except asyncio.CancelledError:
            code, reason = 1011, "Scene stopped"
        except (ConnectionClosed, OSError, InvalidHandshake, TimeoutError):
            code, reason = 1011, "Scene disconnected"
        except WebSocketDisconnect:
            pass
        finally:
            for job in jobs:
                job.cancel()
            await asyncio.gather(*jobs, return_exceptions=True)
            scene.connections.discard(current)
            with suppress(RuntimeError, WebSocketDisconnect, OSError):
                await ws.close(code=code if code not in (1005, 1006, 1015) else 1011, reason=reason)

    def app(self):
        return Starlette(
            lifespan=self.lifespan,
            routes=[
                Route("/", self.index),
                Mount("/_ui/assets", app=StaticFiles(directory=Path(__file__).with_name("assets"))),
                Route("/_ui/fonts/{name}", self.font),
                Route("/{label}", self.redirect),
                WebSocketRoute("/{label}/ws", self.websocket),
                Route("/{label}/{path:path}", self.http),
            ],
        )


def main():
    directory, host, port, descriptor = sys.argv[1:]
    gateway = Gateway(directory, host, int(port))
    config = uvicorn.Config(gateway.app(), log_level="warning", timeout_graceful_shutdown=3, **WS_OPTIONS)
    gateway.server = uvicorn.Server(config)
    with socket.socket(fileno=int(descriptor)) as listener:
        gateway.server.run(sockets=[listener])


if __name__ == "__main__":
    main()
