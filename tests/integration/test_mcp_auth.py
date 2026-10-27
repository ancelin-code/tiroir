"""The `/mcp` endpoint refuses what is not an active member's access token."""

from contextlib import closing
from pathlib import Path
from typing import Any

import httpx2
import pytest
from mcp_support import Firm
from starlette.testclient import TestClient

from tiroir.core import serverdb
from tiroir.server.app import create_app

ORIGIN = "https://testserver"
INITIALIZE: dict[str, Any] = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "0"},
    },
}


def _post(data_dir: Path | str, headers: dict[str, str]) -> httpx2.Response:
    app = create_app(data_dir, origin=ORIGIN)
    with TestClient(app, base_url=ORIGIN) as client:
        return client.post(
            "/mcp",
            json=INITIALIZE,
            headers={"Accept": "application/json, text/event-stream", **headers},
        )


def _assert_challenge(response: httpx2.Response) -> None:
    assert response.status_code == 401
    header = response.headers["www-authenticate"]
    assert header.startswith("Bearer ")
    assert (
        f'resource_metadata="{ORIGIN}/.well-known/oauth-protected-resource"' in header
    )


@pytest.mark.parametrize(
    "headers",
    [{}, {"Authorization": "Bearer tir_at_not-a-token"}],
    ids=["no token", "invalid token"],
)
def test_request_without_a_valid_token_gets_the_challenge(
    firm: Firm, headers: dict[str, str]
) -> None:
    # Given
    # When
    response = _post(firm.data_dir, headers)

    # Then
    _assert_challenge(response)


def test_token_of_a_disabled_member_gets_the_challenge(firm: Firm) -> None:
    # Given
    data_dir = firm.data_dir
    token = firm.tokens["carol"]

    # When
    response = _post(data_dir, {"Authorization": f"Bearer {token}"})

    # Then
    _assert_challenge(response)


def test_token_of_an_active_member_is_let_through(firm: Firm) -> None:
    # Given
    data_dir = firm.data_dir
    token = firm.tokens["alice"]

    # When
    response = _post(data_dir, {"Authorization": f"Bearer {token}"})

    # Then
    assert response.status_code == 200
    assert '"name":"tiroir"' in response.text


def test_member_disabled_after_getting_a_token_is_refused_at_the_next_request(
    firm: Firm,
) -> None:
    # Given
    data_dir = firm.data_dir
    token = firm.tokens["alice"]
    with closing(serverdb.open_server_db(data_dir)) as conn:
        serverdb.disable_member(conn, "alice")

    # When
    response = _post(data_dir, {"Authorization": f"Bearer {token}"})

    # Then
    _assert_challenge(response)
