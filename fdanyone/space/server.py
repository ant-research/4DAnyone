"""Serve the Gradio Space at the server root."""

import asyncio
from contextlib import asynccontextmanager

import gradio as gr

from fdanyone.web import create_app as create_root

from .jobs import JobManager
from .theme import CSS, THEME
from .ui import build_space


def create_app(config, *, server_name="127.0.0.1", server_port=7860):
    app = create_root()
    manager = JobManager(config)
    original_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(app):
        try:
            async with original_lifespan(app):
                yield
        finally:
            await asyncio.to_thread(manager.close)

    app.router.lifespan_context = lifespan
    try:
        space = build_space(manager)
        space.queue(default_concurrency_limit=8, max_size=32)
        return gr.mount_gradio_app(
            app,
            space,
            path="/",
            server_name=server_name,
            server_port=server_port,
            ssr_mode=False,
            css=CSS,
            theme=THEME,
            allowed_paths=[str(config.cache_dir)],
            max_file_size="500mb",
            show_error=True,
        )
    except BaseException:
        manager.close()
        raise
