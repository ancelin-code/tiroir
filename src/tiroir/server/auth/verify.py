"""Resolve a bearer token to its member, read again on every request (ADR-015).

No access decision is carried inside a token: a request is accepted only while
the token is unexpired and its member is not disabled, so disabling a member
takes effect at their next request.
"""

import sqlite3
import time
from contextlib import closing
from pathlib import Path
from typing import override

from mcp.server.auth.middleware.bearer_auth import (
    BearerAuthBackend,
    RequireAuthMiddleware,
)
from mcp.server.auth.provider import AccessToken, TokenVerifier
from pydantic import AnyHttpUrl
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.types import ASGIApp

from tiroir.core import serverdb
from tiroir.core.serverdb import Member, OAuthGrant, open_server_db, secret_digest

MCP_PATH = "/mcp"
RESOURCE_METADATA_PATH = "/.well-known/oauth-protected-resource"


def _access(
    conn: sqlite3.Connection, token: str
) -> tuple[Member, OAuthGrant, int] | None:
    found = serverdb.oauth_token(conn, secret_digest(token), "access", time.time())
    if found is None:
        return None
    grant, expires = found
    member = serverdb.active_member(conn, grant.member)
    return None if member is None else (member, grant, expires)


def member_for_token(conn: sqlite3.Connection, token: str) -> Member | None:
    """The member an access token was issued to, only if they are active."""
    found = _access(conn, token)
    return None if found is None else found[0]


class MemberTokenVerifier(TokenVerifier):
    """The MCP SDK's token check, answered from `server.db`."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir

    @override
    async def verify_token(self, token: str) -> AccessToken | None:
        with closing(open_server_db(self.data_dir)) as conn:
            found = _access(conn, token)
        if found is None:
            return None
        member, grant, expires = found
        return AccessToken(
            token=token,
            client_id=grant.client_id,
            scopes=list(grant.scopes),
            expires_at=expires,
            resource=grant.resource,
            subject=member.id,
        )


def require_member(app: ASGIApp, data_dir: Path, origin: str) -> ASGIApp:
    """Let a request reach `app` only with an active member's access token.

    Anything else gets `401` with `WWW-Authenticate: Bearer
    resource_metadata="<origin>/.well-known/oauth-protected-resource"`, the
    start of the MCP authorization flow.
    """
    return AuthenticationMiddleware(
        RequireAuthMiddleware(app, [], AnyHttpUrl(origin + RESOURCE_METADATA_PATH)),
        backend=BearerAuthBackend(
            MemberTokenVerifier(data_dir),
            resource_server_url=AnyHttpUrl(origin + MCP_PATH),
        ),
    )
