"""HTTP server for the Gradio Space."""

from fastapi import FastAPI


def create_app():
    return FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


def serve(app, *, host="127.0.0.1", port=7860):
    import uvicorn

    config = uvicorn.Config(app, host=host, port=port, log_level="warning", timeout_graceful_shutdown=5)
    # Detect a busy port before starting the application lifespan.
    with config.bind_socket() as sock:
        print(f"Starting http://{host}:{sock.getsockname()[1]}/", flush=True)
        uvicorn.Server(config).run(sockets=[sock])
