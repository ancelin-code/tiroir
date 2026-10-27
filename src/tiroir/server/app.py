"""The Starlette application: `/health`, sign-in, OAuth, `/mcp`, the request log."""

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import version
from os import environ
from pathlib import Path

import httpx
from loguru import logger
from mcp.server.auth.middleware.auth_context import AuthContextMiddleware
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from tiroir.core import Core, open_core
from tiroir.server.auth.oauth import (
    ClientMetadataDocuments,
    Resolver,
    TiroirProvider,
    oauth_routes,
    resolve,
)
from tiroir.server.auth.pages import page_routes
from tiroir.server.auth.verify import MCP_PATH, require_member
from tiroir.server.logging import configure_logging
from tiroir.server.mcp import build_server

DEFAULT_DATA_DIR = "/data"
DEFAULT_DOMAIN = "localhost"


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


def create_app(
    core_or_data_dir: Path | str,
    *,
    origin: str = f"https://{DEFAULT_DOMAIN}",
    http_transport: httpx.AsyncBaseTransport | None = None,
    resolver: Resolver = resolve,
) -> Starlette:
    """Build the application on a data directory, served at `origin`.

    `origin` is the public address behind Caddy, the OAuth issuer;
    `http_transport` carries the fetches of client metadata documents and
    `resolver` resolves their host names (a test serves its own). `/mcp` is
    the MCP endpoint, open to the access tokens of active members only.
    """
    data_dir = Path(core_or_data_dir)
    documents = ClientMetadataDocuments(http_transport, resolver)
    provider = TiroirProvider(data_dir, origin, documents)

    def core() -> Core:
        return app.state.core

    async def mcp_endpoint(scope: Scope, receive: Receive, send: Send) -> None:
        await app.state.mcp_app(scope, receive, send)

    @asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        app.state.core = open_core(data_dir)  # creates server.db, migrates it
        try:
            # A session manager runs once, so each start builds its own MCP app.
            # Caddy owns the Host check; the bearer token is the access control.
            app.state.mcp_app = build_server(core).streamable_http_app(
                streamable_http_path=MCP_PATH,
                transport_security=TransportSecuritySettings(
                    enable_dns_rebinding_protection=False
                ),
            )
            async with app.state.mcp_app.router.lifespan_context(app.state.mcp_app):
                app.state.ready = True
                yield
        finally:
            app.state.ready = False
            app.state.core.close()

    app = Starlette(
        routes=[
            Route("/health", health, methods=["GET"]),
            Route(
                MCP_PATH,
                require_member(AuthContextMiddleware(mcp_endpoint), data_dir, origin),
                methods=["POST", "GET", "DELETE"],
            ),
            *oauth_routes(provider),
            *page_routes(provider),
        ],
        lifespan=lifespan,
    )
    app.state.ready = False
    app.state.data_dir = data_dir
    app.add_middleware(RequestLogMiddleware)
    return app


def app_from_env() -> Starlette:
    """Uvicorn's application factory: logging, then the app on `TIROIR_DATA`.

    The public origin is `https://` and `TIROIR_DOMAIN`, the domain Caddy serves.
    """
    configure_logging()
    return create_app(
        environ.get("TIROIR_DATA", DEFAULT_DATA_DIR),
        origin=f"https://{environ.get('TIROIR_DOMAIN', DEFAULT_DOMAIN)}",
    )
