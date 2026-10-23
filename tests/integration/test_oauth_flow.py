import base64
import hashlib
import ipaddress
import logging
import re
import secrets
from collections.abc import Iterator
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import httpx2  # the HTTP client of Starlette's TestClient
import pytest
from loguru import logger
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient
from starlette.types import Receive, Scope, Send

from tiroir.cli.main import main
from tiroir.core import serverdb
from tiroir.server.app import create_app
from tiroir.server.auth.oauth import IPAddress
from tiroir.server.auth.sessions import CSRF_COOKIE
from tiroir.server.auth.verify import require_member

ORIGIN = "https://testserver"
CIMD_URL = "https://client.example/oauth/client.json"
REDIRECT_URI = "http://127.0.0.1:33418/callback"
PASSWORD = "alice's long password"


async def _resolve(host: str) -> list[IPAddress]:
    return [ipaddress.ip_address("93.184.215.14")]


def _serve_documents(request: httpx.Request) -> httpx.Response:
    if f"https://{request.headers['Host']}{request.url.path}" != CIMD_URL:
        return httpx.Response(404)
    document = {
        "client_id": CIMD_URL,
        "client_name": "Test Client",
        "redirect_uris": [REDIRECT_URI],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
    }
    return httpx.Response(200, json=document)


async def _protected(scope: Scope, receive: Receive, send: Send) -> None:
    await JSONResponse({"ok": True})(scope, receive, send)


@dataclass
class Server:
    client: TestClient
    data_dir: Path


@pytest.fixture
def server(tmp_path: Path) -> Iterator[Server]:
    app = create_app(
        tmp_path,
        origin=ORIGIN,
        http_transport=httpx.MockTransport(_serve_documents),
        resolver=_resolve,
    )
    app.router.routes.append(
        Route("/protected", require_member(_protected, tmp_path, ORIGIN))
    )
    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as client:
        with closing(serverdb.open_server_db(tmp_path)) as conn:
            serverdb.create_member(
                conn, "alice", "Alice", PASSWORD, must_change_password=False
            )
        yield Server(client, tmp_path)


def _pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    digest = hashlib.sha256(verifier.encode()).digest()
    return verifier, base64.urlsafe_b64encode(digest).decode().rstrip("=")


def _query(url: str) -> dict[str, str]:
    return {key: values[0] for key, values in parse_qs(urlsplit(url).query).items()}


def _sign_in(client: TestClient, next_path: str = "/signin") -> httpx2.Response:
    client.get("/signin")
    return client.post(
        "/signin",
        data={
            "csrf": client.cookies[CSRF_COOKIE],
            "handle": "alice",
            "password": PASSWORD,
            "next": next_path,
        },
    )


def _authorize_params(client_id: str, challenge: str, **extra: str) -> dict[str, str]:
    return {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": "state-1",
        "resource": f"{ORIGIN}/mcp",
        **extra,
    }


def _code(client: TestClient, client_id: str, challenge: str) -> str:
    """Authorize as a signed-in Alice who consents; the code the client gets."""
    authorize = client.get(
        "/oauth/authorize", params=_authorize_params(client_id, challenge)
    )
    consent = _query(authorize.headers["location"])["consent"]
    answer = client.post(
        "/oauth/authorize",
        data={
            "csrf": client.cookies[CSRF_COOKIE],
            "consent": consent,
            "decision": "approve",
        },
    )
    return _query(answer.headers["location"])["code"]


def _exchange(
    client: TestClient, client_id: str, code: str, verifier: str, **extra: str
) -> httpx2.Response:
    return client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": client_id,
            "code_verifier": verifier,
            **extra,
        },
    )


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@dataclass
class Flow:
    challenge: httpx2.Response
    resource_metadata: dict[str, Any]
    server_metadata: dict[str, Any]
    signin_redirect: httpx2.Response
    consent_page: httpx2.Response
    callback: dict[str, str]
    tokens: dict[str, Any]
    first_call: httpx2.Response
    refreshed: dict[str, Any]
    call_after_refresh: dict[str, int]
    old_refresh: httpx2.Response


def _play_client(
    client: TestClient, client_id: str, client_secret: str | None = None
) -> Flow:
    """What an MCP client does, from the first `401` to a refreshed token."""
    secret = {} if client_secret is None else {"client_secret": client_secret}
    challenge = client.get("/protected")
    match = re.search(
        r'resource_metadata="([^"]+)"', challenge.headers["www-authenticate"]
    )
    assert match is not None
    resource_metadata = client.get(match.group(1)).json()
    issuer = resource_metadata["authorization_servers"][0]
    server_metadata = client.get(
        f"{issuer}/.well-known/oauth-authorization-server"
    ).json()
    verifier, code_challenge = _pkce()

    authorize = client.get(
        server_metadata["authorization_endpoint"],
        params=_authorize_params(client_id, code_challenge),
    )
    consent_url = authorize.headers["location"]
    signin_redirect = client.get(consent_url)
    signed_in = _sign_in(client, _query(signin_redirect.headers["location"])["next"])
    consent_page = client.get(signed_in.headers["location"])
    approved = client.post(
        server_metadata["authorization_endpoint"],
        data={
            "csrf": client.cookies[CSRF_COOKIE],
            "consent": _query(consent_url)["consent"],
            "decision": "approve",
        },
    )
    callback = _query(approved.headers["location"])
    tokens = _exchange(client, client_id, callback["code"], verifier, **secret).json()
    first_call = client.get("/protected", headers=_bearer(tokens["access_token"]))

    refresh = {
        "grant_type": "refresh_token",
        "refresh_token": tokens["refresh_token"],
        "client_id": client_id,
        **secret,
    }
    refreshed = client.post(server_metadata["token_endpoint"], data=refresh).json()
    call_after_refresh = {
        "old": client.get(
            "/protected", headers=_bearer(tokens["access_token"])
        ).status_code,
        "new": client.get(
            "/protected", headers=_bearer(refreshed["access_token"])
        ).status_code,
    }
    old_refresh = client.post(server_metadata["token_endpoint"], data=refresh)
    return Flow(
        challenge,
        resource_metadata,
        server_metadata,
        signin_redirect,
        consent_page,
        callback,
        tokens,
        first_call,
        refreshed,
        call_after_refresh,
        old_refresh,
    )


def _assert_full_flow(flow: Flow) -> None:
    assert flow.challenge.status_code == 401
    assert flow.resource_metadata["resource"] == f"{ORIGIN}/mcp"
    assert flow.server_metadata["issuer"] == ORIGIN
    assert flow.server_metadata["client_id_metadata_document_supported"] is True
    assert flow.server_metadata["code_challenge_methods_supported"] == ["S256"]
    assert flow.signin_redirect.status_code == 303
    assert flow.signin_redirect.headers["location"].startswith("/signin?next=")
    assert flow.consent_page.status_code == 200
    assert flow.callback["state"] == "state-1"
    assert flow.callback["iss"] == ORIGIN
    assert flow.tokens["token_type"] == "Bearer"
    assert flow.tokens["expires_in"] == 3600
    assert flow.first_call.status_code == 200
    assert flow.first_call.json() == {"ok": True}
    assert flow.refreshed["refresh_token"] != flow.tokens["refresh_token"]
    assert flow.call_after_refresh == {"old": 401, "new": 200}
    assert flow.old_refresh.status_code == 400
    assert flow.old_refresh.json()["error"] == "invalid_grant"


def test_client_registered_by_metadata_document_plays_full_flow(
    server: Server,
) -> None:
    # Given
    client = server.client

    # When
    flow = _play_client(client, CIMD_URL)

    # Then
    _assert_full_flow(flow)
    assert "Test Client" in flow.consent_page.text
    assert flow.challenge.headers["www-authenticate"].startswith("Bearer ")
    assert (
        f'resource_metadata="{ORIGIN}/.well-known/oauth-protected-resource"'
        in flow.challenge.headers["www-authenticate"]
    )


def test_client_registered_dynamically_plays_full_flow(server: Server) -> None:
    # Given
    client = server.client
    registered = client.post(
        "/oauth/register",
        json={"client_name": "Registered Client", "redirect_uris": [REDIRECT_URI]},
    ).json()

    # When
    flow = _play_client(client, registered["client_id"], registered["client_secret"])

    # Then
    _assert_full_flow(flow)
    assert "Registered Client" in flow.consent_page.text


def test_dynamic_client_without_its_secret_is_refused(server: Server) -> None:
    # Given
    client = server.client
    registered = client.post(
        "/oauth/register", json={"redirect_uris": [REDIRECT_URI]}
    ).json()
    _sign_in(client)
    verifier, challenge = _pkce()
    code = _code(client, registered["client_id"], challenge)

    # When
    answer = _exchange(
        client, registered["client_id"], code, verifier, client_secret="guess"
    )

    # Then
    assert answer.status_code == 401
    assert answer.json()["error"] == "invalid_client"


def test_code_exchange_with_wrong_verifier_is_refused(server: Server) -> None:
    # Given
    client = server.client
    _sign_in(client)
    _, challenge = _pkce()
    code = _code(client, CIMD_URL, challenge)
    other_verifier, _ = _pkce()

    # When
    answer = _exchange(client, CIMD_URL, code, other_verifier)

    # Then
    assert answer.status_code == 400
    assert answer.json()["error"] == "invalid_grant"


def test_plain_code_challenge_is_refused(server: Server) -> None:
    # Given
    client = server.client
    verifier, _ = _pkce()
    params = _authorize_params(CIMD_URL, verifier, code_challenge_method="plain")

    # When
    answer = client.get("/oauth/authorize", params=params)

    # Then
    assert answer.status_code == 302
    location = answer.headers["location"]
    assert location.startswith(REDIRECT_URI)
    assert _query(location)["error"] == "invalid_request"
    assert "consent" not in location


def test_redirect_uri_outside_client_metadata_is_refused(server: Server) -> None:
    # Given
    client = server.client
    _, challenge = _pkce()
    params = _authorize_params(
        CIMD_URL, challenge, redirect_uri="https://attacker.example/callback"
    )

    # When
    answer = client.get("/oauth/authorize", params=params)

    # Then
    assert answer.status_code == 400
    assert answer.json()["error"] == "invalid_request"
    assert "location" not in answer.headers


def test_code_exchange_with_another_redirect_uri_is_refused(server: Server) -> None:
    # Given
    client = server.client
    _sign_in(client)
    verifier, challenge = _pkce()
    code = _code(client, CIMD_URL, challenge)

    # When
    answer = _exchange(
        client, CIMD_URL, code, verifier, redirect_uri="http://127.0.0.1:1/other"
    )

    # Then
    assert answer.status_code == 400
    assert answer.json()["error"] == "invalid_request"


def test_expired_code_is_refused(server: Server) -> None:
    # Given
    client = server.client
    _sign_in(client)
    verifier, challenge = _pkce()
    code = _code(client, CIMD_URL, challenge)
    with closing(serverdb.open_server_db(server.data_dir)) as conn:
        conn.execute("UPDATE oauth_codes SET expires = 0")

    # When
    answer = _exchange(client, CIMD_URL, code, verifier)

    # Then
    assert answer.status_code == 400
    assert answer.json() == {
        "error": "invalid_grant",
        "error_description": "authorization code has expired",
    }


def test_code_works_only_once(server: Server) -> None:
    # Given
    client = server.client
    _sign_in(client)
    verifier, challenge = _pkce()
    code = _code(client, CIMD_URL, challenge)
    _exchange(client, CIMD_URL, code, verifier)

    # When
    answer = _exchange(client, CIMD_URL, code, verifier)

    # Then
    assert answer.status_code == 400
    assert answer.json()["error"] == "invalid_grant"


def test_denied_consent_returns_access_denied(server: Server) -> None:
    # Given
    client = server.client
    _sign_in(client)
    _, challenge = _pkce()
    authorize = client.get(
        "/oauth/authorize", params=_authorize_params(CIMD_URL, challenge)
    )
    consent = _query(authorize.headers["location"])["consent"]

    # When
    answer = client.post(
        "/oauth/authorize",
        data={"csrf": client.cookies[CSRF_COOKIE], "consent": consent},
    )

    # Then
    assert _query(answer.headers["location"]) == {
        "error": "access_denied",
        "state": "state-1",
        "iss": ORIGIN,
    }


def test_consent_without_csrf_token_is_refused(server: Server) -> None:
    # Given
    client = server.client
    _sign_in(client)
    _, challenge = _pkce()
    authorize = client.get(
        "/oauth/authorize", params=_authorize_params(CIMD_URL, challenge)
    )
    consent = _query(authorize.headers["location"])["consent"]

    # When
    answer = client.post(
        "/oauth/authorize", data={"consent": consent, "decision": "approve"}
    )

    # Then
    assert answer.status_code == 403
    assert "location" not in answer.headers


def test_disabled_member_token_is_refused_at_once(
    server: Server, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given
    client = server.client
    monkeypatch.setenv("TIROIR_DATA", str(server.data_dir))
    _sign_in(client)
    verifier, challenge = _pkce()
    code = _code(client, CIMD_URL, challenge)
    access = _exchange(client, CIMD_URL, code, verifier).json()["access_token"]
    before = client.get("/protected", headers=_bearer(access))
    main(["admin", "members", "disable", "alice"])

    # When
    answer = client.get("/protected", headers=_bearer(access))

    # Then
    assert before.status_code == 200
    assert answer.status_code == 401
    assert (
        f'resource_metadata="{ORIGIN}/.well-known/oauth-protected-resource"'
        in answer.headers["www-authenticate"]
    )


def _refresh(client: TestClient, refresh_token: str) -> httpx2.Response:
    return client.post(
        "/oauth/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": CIMD_URL,
        },
    )


def test_disabled_member_token_cannot_be_refreshed(
    server: Server, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given
    client = server.client
    monkeypatch.setenv("TIROIR_DATA", str(server.data_dir))
    _sign_in(client)
    verifier, challenge = _pkce()
    code = _code(client, CIMD_URL, challenge)
    refresh = _exchange(client, CIMD_URL, code, verifier).json()["refresh_token"]
    main(["admin", "members", "disable", "alice"])

    # When
    answer = _refresh(client, refresh)

    # Then
    assert answer.status_code == 400
    assert answer.json()["error"] == "invalid_grant"


def test_expired_access_token_is_refused(server: Server) -> None:
    # Given
    client = server.client
    _sign_in(client)
    verifier, challenge = _pkce()
    code = _code(client, CIMD_URL, challenge)
    access = _exchange(client, CIMD_URL, code, verifier).json()["access_token"]
    with closing(serverdb.open_server_db(server.data_dir)) as conn:
        conn.execute("UPDATE oauth_tokens SET expires = 0 WHERE kind = 'access'")

    # When
    answer = client.get("/protected", headers=_bearer(access))

    # Then
    assert answer.status_code == 401


def test_expired_refresh_token_is_refused(server: Server) -> None:
    # Given
    client = server.client
    _sign_in(client)
    verifier, challenge = _pkce()
    code = _code(client, CIMD_URL, challenge)
    refresh = _exchange(client, CIMD_URL, code, verifier).json()["refresh_token"]
    with closing(serverdb.open_server_db(server.data_dir)) as conn:
        conn.execute("UPDATE oauth_tokens SET expires = 0 WHERE kind = 'refresh'")

    # When
    answer = _refresh(client, refresh)

    # Then
    assert answer.status_code == 400
    assert answer.json()["error"] == "invalid_grant"


def test_revoked_token_is_refused(server: Server) -> None:
    # Given
    client = server.client
    _sign_in(client)
    verifier, challenge = _pkce()
    code = _code(client, CIMD_URL, challenge)
    tokens = _exchange(client, CIMD_URL, code, verifier).json()

    # The SDK's revocation request requires the field, empty for a public client.
    revocation = {
        "token": tokens["access_token"],
        "client_id": CIMD_URL,
        "client_secret": "",
    }

    # When
    revoked = client.post("/oauth/revoke", data=revocation)

    # Then
    assert revoked.status_code == 200
    assert (
        client.get("/protected", headers=_bearer(tokens["access_token"])).status_code
        == 401
    )
    assert _refresh(client, tokens["refresh_token"]).status_code == 400


def test_tokens_and_passwords_stay_out_of_logs_and_database(
    server: Server, caplog: pytest.LogCaptureFixture
) -> None:
    # Given
    client = server.client
    records: list[str] = []
    sink = logger.add(
        lambda m: records.append(f"{m} {m.record['extra']}"), level="DEBUG"
    )
    caplog.set_level(logging.DEBUG)
    registered = client.post(
        "/oauth/register", json={"redirect_uris": [REDIRECT_URI]}
    ).json()

    # When
    flow = _play_client(client, registered["client_id"], registered["client_secret"])
    logger.remove(sink)

    # Then
    secrets_seen = [
        PASSWORD,
        registered["client_secret"],
        flow.callback["code"],
        flow.tokens["access_token"],
        flow.tokens["refresh_token"],
        flow.refreshed["access_token"],
        flow.refreshed["refresh_token"],
        client.cookies["__Host-tiroir_session"],
    ]
    logs = "\n".join(records) + caplog.text
    database = (server.data_dir / "server.db").read_bytes()
    for secret in secrets_seen:
        assert secret not in logs
        assert secret.encode() not in database
