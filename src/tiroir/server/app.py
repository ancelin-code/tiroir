"""The Starlette application: `/health` and the JSON request log."""

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import version
from os import environ
from pathlib import Path

from loguru import logger
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from tiroir.core.serverdb import open_server_db
from tiroir.server.logging import configure_logging

DEFAULT_DATA_DIR = "/data"


class RequestLogMiddleware:
    """Log one line per request: never a query string, a body or a raw path."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = time.perf_counter()
        status = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            route = scope.get("route")
            logger.bind(
                method=scope["method"],
                path=getattr(route, "path", "<unmatched>"),
                status=status,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
                member=scope.get("state", {}).get("member_handle", ""),
            ).info("request")


async def health(request: Request) -> Response:
    if not request.app.state.ready:
        return JSONResponse({"status": "starting", "version": version("tiroir")}, 503)
    return JSONResponse({"status": "ready", "version": version("tiroir")})


def create_app(core_or_data_dir: Path | str) -> Starlette:
    """Build the application on a data directory.

    The core facade arrives with the stores (server-003); until then the
    data directory is the only thing the server needs.
    """
    data_dir = Path(core_or_data_dir)

    @asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        open_server_db(data_dir).close()  # creates it, applies the migrations
        app.state.ready = True
        yield
        app.state.ready = False

    app = Starlette(
        routes=[Route("/health", health, methods=["GET"])],
        lifespan=lifespan,
    )
    app.state.ready = False
    app.state.data_dir = data_dir
    app.add_middleware(RequestLogMiddleware)
    return app


def app_from_env() -> Starlette:
    """Uvicorn's application factory: logging, then the app on `TIROIR_DATA`."""
    configure_logging()
    return create_app(environ.get("TIROIR_DATA", DEFAULT_DATA_DIR))
