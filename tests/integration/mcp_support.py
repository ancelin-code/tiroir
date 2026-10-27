"""A data directory with members and tokens, and MCP sessions against it."""

import secrets
import time
from collections.abc import Awaitable, Callable
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import anyio
import httpx2  # the HTTP client of the MCP SDK
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from tiroir.core import serverdb
from tiroir.server.app import create_app

MCP_ORIGIN = "https://testserver"
Scenario = Callable[[Client], Awaitable[Any]]


@dataclass(frozen=True)
class Firm:
    """A data directory with Alice (granted `cabinet`), Bob (no grant) and tokens."""

    data_dir: Path
    tokens: dict[str, str]

    def run(self, handle: str, scenario: Scenario) -> Any:
        """Open an MCP session as `handle` against a fresh app and run `scenario`."""
        return anyio.run(self._session, self.tokens[handle], scenario)

    async def _session(self, token: str, scenario: Scenario) -> Any:
        app = create_app(self.data_dir, origin=MCP_ORIGIN)
        async with app.router.lifespan_context(app):
            http = httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app=app),
                base_url=MCP_ORIGIN,
                headers={"Authorization": f"Bearer {token}"},
            )
            async with http:
                transport = streamable_http_client(
                    MCP_ORIGIN + "/mcp", http_client=http
                )
                async with Client(transport) as client:
                    return await scenario(client)


def mint_token(data_dir: Path, member_id: str) -> str:
    """An access token of the member, as the OAuth flow would have issued."""
    token = "tir_at_" + secrets.token_urlsafe(16)
    grant = serverdb.OAuthGrant(
        secrets.token_hex(8), "client", member_id, (), MCP_ORIGIN + "/mcp"
    )
    hashed = serverdb.OAuthTokenHash(
        serverdb.secret_digest(token), "access", int(time.time()) + 3600
    )
    with closing(serverdb.open_server_db(data_dir)) as conn:
        serverdb.save_oauth_tokens(conn, grant, [hashed])
    return token
