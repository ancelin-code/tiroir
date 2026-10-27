"""A client plays the whole flow: sign in, authorize, open an MCP session, use it."""

import base64
import hashlib
import re
import secrets
import time
from collections.abc import Awaitable, Callable
from contextlib import closing
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import anyio
import httpx2  # the HTTP client of the MCP SDK
from mcp import Client
from mcp.client.streamable_http import streamable_http_client

from tiroir.core import Audience, open_core, serverdb
from tiroir.server.app import create_app
from tiroir.server.auth.sessions import CSRF_COOKIE

ORIGIN = "https://testserver"
REDIRECT_URI = "http://127.0.0.1:33418/callback"
PASSWORD = "alice's long password"
PRESET = Path(__file__).resolve().parents[2] / "presets" / "accounting-firm"
CLIENT = "cabinet:clients/c001"
SEARCH_DEADLINE = 2.0


def _query(url: str) -> dict[str, str]:
    return {key: values[0] for key, values in parse_qs(urlsplit(url).query).items()}


async def _authorize(http: httpx2.AsyncClient) -> str:
    """What an MCP client does from the first `401`: the access token it ends with."""
    challenge = await http.post("/mcp", json={})
    metadata_url = re.search(
        r'resource_metadata="([^"]+)"', challenge.headers["www-authenticate"]
    )
    assert challenge.status_code == 401 and metadata_url is not None
    resource = (await http.get(metadata_url.group(1))).json()
    server = (
        await http.get(
            resource["authorization_servers"][0]
            + "/.well-known/oauth-authorization-server"
        )
    ).json()
    registered = (
        await http.post(
            server["registration_endpoint"],
            json={"client_name": "End To End", "redirect_uris": [REDIRECT_URI]},
        )
    ).json()
    verifier = secrets.token_urlsafe(48)
    challenge_s256 = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .decode()
        .rstrip("=")
    )
    params = {
        "response_type": "code",
        "client_id": registered["client_id"],
        "redirect_uri": REDIRECT_URI,
        "code_challenge": challenge_s256,
        "code_challenge_method": "S256",
        "state": "s",
        "resource": resource["resource"],
    }
    redirect = await http.get(server["authorization_endpoint"], params=params)
    await http.get("/signin")
    signed_in = await http.post(
        "/signin",
        data={
            "csrf": http.cookies[CSRF_COOKIE],
            "handle": "alice",
            "password": PASSWORD,
            "next": _query(redirect.headers["location"])["next"],
        },
    )
    consent_url = (await http.get(signed_in.headers["location"])).headers["location"]
    approved = await http.post(
        server["authorization_endpoint"],
        data={
            "csrf": http.cookies[CSRF_COOKIE],
            "consent": _query(consent_url)["consent"],
            "decision": "approve",
        },
    )
    tokens = await http.post(
        server["token_endpoint"],
        data={
            "grant_type": "authorization_code",
            "code": _query(approved.headers["location"])["code"],
            "redirect_uri": REDIRECT_URI,
            "client_id": registered["client_id"],
            "client_secret": registered["client_secret"],
            "code_verifier": verifier,
        },
    )
    return tokens.json()["access_token"]


async def _play(data_dir: Path, scenario: Callable[[Client], Awaitable[Any]]) -> Any:
    app = create_app(data_dir, origin=ORIGIN)
    async with app.router.lifespan_context(app):
        transport = httpx2.ASGITransport(app=app)
        async with httpx2.AsyncClient(transport=transport, base_url=ORIGIN) as http:
            token = await _authorize(http)
            http.headers["Authorization"] = f"Bearer {token}"
            stream = streamable_http_client(ORIGIN + "/mcp", http_client=http)
            async with Client(stream) as client:
                return await scenario(client)


def test_member_signs_in_and_finds_what_they_just_logged(tmp_path: Path) -> None:
    # Given
    with closing(serverdb.open_server_db(tmp_path)) as conn:
        serverdb.create_member(conn, "root", "Root", "pw", is_admin=True)
        serverdb.create_member(
            conn, "alice", "Alice Martin", PASSWORD, must_change_password=False
        )
    core = open_core(tmp_path, start_workers=False)
    core.admin("root").create_store(
        "cabinet", Audience.PERSONAL, "fr", owner="alice", preset=PRESET
    )
    core.close()

    async def scenario(client: Client) -> dict[str, Any]:
        tools = [t.name for t in (await client.list_tools()).tools]
        drawers = await client.call_tool("tiroir_read", {"what": "drawers"})
        written = await client.call_tool(
            "tiroir_write",
            {"action": "log", "drawer": CLIENT, "text": "Relance zephyrine."},
        )
        started = time.monotonic()
        found: dict[str, Any] = {"hits": []}
        while not found["hits"] and time.monotonic() - started < SEARCH_DEADLINE:
            result = await client.call_tool(
                "tiroir_search", {"query": "zephyrine", "drawers": [CLIENT]}
            )
            found = result.structured_content or {}
            await anyio.sleep(0.05)
        return {
            "tools": tools,
            "drawers": drawers.structured_content,
            "written": written.structured_content,
            "found": found,
            "elapsed": time.monotonic() - started,
        }

    # When
    played = anyio.run(_play, tmp_path, scenario)

    # Then
    assert sorted(played["tools"]) == [
        "tiroir_read",
        "tiroir_search",
        "tiroir_status",
        "tiroir_write",
    ]
    assert CLIENT.split(":")[1] in {d["drawer"] for d in played["drawers"]["drawers"]}
    assert played["written"]["applied"] is True
    [hit, *_] = played["found"]["hits"]
    assert (hit["store"], hit["drawer"], hit["kind"]) == (
        "cabinet",
        "clients/c001",
        "log",
    )
    assert hit["path"].startswith("clients/c001/log/")
    assert hit["date"] and hit["author"] == "alice"
    assert played["elapsed"] < SEARCH_DEADLINE
