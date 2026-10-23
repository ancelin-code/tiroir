from collections.abc import Iterator
from contextlib import closing
from pathlib import Path
from typing import cast

import httpx2  # the HTTP client of Starlette's TestClient
import pytest
import uvicorn
from starlette.testclient import TestClient
from starlette.types import ASGIApp

from tiroir.cli.admin import proxy_options, trusted_proxies
from tiroir.core import serverdb
from tiroir.server.app import create_app
from tiroir.server.auth.sessions import CSRF_COOKIE, SESSION_COOKIE

ORIGIN = "https://testserver"
INITIAL = "initial-password"
CHOSEN = "my own long password"
CADDY = "172.30.80.2"  # on the Compose network tiroir trusts


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def client(data_dir: Path) -> Iterator[TestClient]:
    app = create_app(data_dir, origin=ORIGIN)
    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as client:
        with closing(serverdb.open_server_db(data_dir)) as conn:
            serverdb.create_member(conn, "alice", "Alice", INITIAL)
        yield client


def _sign_in(
    client: TestClient,
    password: str,
    handle: str = "alice",
    next_path: str = "/x",
    forwarded_for: str | None = None,
) -> httpx2.Response:
    headers = {} if forwarded_for is None else {"X-Forwarded-For": forwarded_for}
    client.get("/signin", headers=headers)
    return client.post(
        "/signin",
        data={
            "csrf": client.cookies[CSRF_COOKIE],
            "handle": handle,
            "password": password,
            "next": next_path,
        },
        headers=headers,
    )


@pytest.fixture
def served(data_dir: Path) -> uvicorn.Config:
    """The application as `tiroir admin serve` runs it, behind the Compose proxy."""
    config = uvicorn.Config(
        create_app(data_dir, origin=ORIGIN),
        log_config=None,
        **proxy_options(trusted_proxies("172.30.80.0/24")),
    )
    config.load()
    with closing(serverdb.open_server_db(data_dir)) as conn:
        serverdb.create_member(
            conn, "alice", "Alice", CHOSEN, must_change_password=False
        )
    return config


def _from(config: uvicorn.Config, peer: str) -> TestClient:
    return TestClient(
        cast(ASGIApp, config.loaded_app),
        base_url=ORIGIN,
        follow_redirects=False,
        client=(peer, 1),
    )


def _change(client: TestClient, password: str, confirm: str) -> httpx2.Response:
    return client.post(
        "/signin",
        data={
            "csrf": client.cookies[CSRF_COOKIE],
            "new_password": password,
            "confirm_password": confirm,
            "next": "/x",
        },
    )


def test_first_sign_in_forces_a_password_change(
    client: TestClient, data_dir: Path
) -> None:
    # Given
    signed_in = _sign_in(client, INITIAL)

    # When
    page = client.get(signed_in.headers["location"])

    # Then
    assert signed_in.status_code == 303
    assert signed_in.headers["location"] == "/signin?next=%2Fx"
    assert page.status_code == 200
    assert 'name="new_password"' in page.text
    with closing(serverdb.open_server_db(data_dir)) as conn:
        member = serverdb.find_member(conn, "alice")
    assert member is not None and member.must_change_password


def test_pages_wait_until_the_password_is_changed(client: TestClient) -> None:
    # Given
    _sign_in(client, INITIAL)

    # When
    page = client.get("/signin", params={"next": "/x"})

    # Then
    assert page.status_code == 200
    assert 'name="new_password"' in page.text
    assert "location" not in page.headers


def test_changed_password_replaces_the_initial_one(
    client: TestClient, data_dir: Path
) -> None:
    # Given
    _sign_in(client, INITIAL)

    # When
    changed = _change(client, CHOSEN, CHOSEN)

    # Then
    assert changed.status_code == 303
    assert changed.headers["location"] == "/x"
    with closing(serverdb.open_server_db(data_dir)) as conn:
        assert serverdb.authenticate(conn, "alice", INITIAL) is None
        member = serverdb.authenticate(conn, "alice", CHOSEN)
    assert member is not None
    assert not member.must_change_password


@pytest.mark.parametrize(
    ("password", "confirm"),
    [("short", "short"), (CHOSEN, CHOSEN + "!"), (INITIAL * 2, INITIAL)],
)
def test_unsuitable_new_password_is_refused(
    client: TestClient, password: str, confirm: str
) -> None:
    # Given
    _sign_in(client, INITIAL)

    # When
    answer = _change(client, password, confirm)

    # Then
    assert answer.status_code == 400
    assert 'role="alert"' in answer.text


def test_password_change_is_refused_once_chosen(
    client: TestClient, data_dir: Path
) -> None:
    # Given
    _sign_in(client, INITIAL)
    _change(client, CHOSEN, CHOSEN)

    # When
    answer = _change(client, "yet another password", "yet another password")

    # Then
    assert answer.status_code == 303
    with closing(serverdb.open_server_db(data_dir)) as conn:
        assert serverdb.authenticate(conn, "alice", CHOSEN) is not None


def test_wrong_password_and_unknown_handle_answer_alike(client: TestClient) -> None:
    # Given
    handles = [("alice", "wrong password"), ("bob", INITIAL)]

    # When
    answers = [_sign_in(client, password, handle) for handle, password in handles]

    # Then
    assert [a.status_code for a in answers] == [400, 400]
    assert answers[0].text == answers[1].text
    assert SESSION_COOKIE not in client.cookies


def test_ten_failures_in_a_minute_throttle_the_handle(client: TestClient) -> None:
    # Given
    for _ in range(10):
        _sign_in(client, "wrong password")

    # When
    answer = _sign_in(client, INITIAL)

    # Then
    assert answer.status_code == 429
    assert SESSION_COOKIE not in client.cookies


def test_nine_failures_do_not_throttle(client: TestClient) -> None:
    # Given
    for _ in range(9):
        _sign_in(client, "wrong password")

    # When
    answer = _sign_in(client, INITIAL)

    # Then
    assert answer.status_code == 303


def test_failures_from_one_address_do_not_block_another(
    served: uvicorn.Config,
) -> None:
    # Given
    with _from(served, CADDY) as caddy:
        for index in range(30):
            _sign_in(caddy, "wrong", f"member{index}", forwarded_for="198.51.100.1")
        blocked = _sign_in(caddy, CHOSEN, forwarded_for="198.51.100.1")
        caddy.cookies.clear()

        # When
        answer = _sign_in(caddy, CHOSEN, forwarded_for="198.51.100.2")

    # Then
    assert blocked.status_code == 429
    assert answer.status_code == 303


def test_forwarded_for_from_an_untrusted_peer_is_ignored(
    served: uvicorn.Config,
) -> None:
    # Given
    with _from(served, "203.0.113.7") as outsider:
        for index in range(30):
            _sign_in(
                outsider, "wrong", f"member{index}", forwarded_for=f"10.0.0.{index}"
            )

        # When
        answer = _sign_in(outsider, CHOSEN, forwarded_for="10.0.0.99")

    # Then
    assert answer.status_code == 429


def test_member_signs_in_while_an_attacker_on_the_handle_is_throttled(
    served: uvicorn.Config,
) -> None:
    # Given
    with _from(served, CADDY) as attacker, _from(served, CADDY) as alice:
        for _ in range(10):
            _sign_in(attacker, "guess", forwarded_for="198.51.100.66")
        throttled = _sign_in(attacker, CHOSEN, forwarded_for="198.51.100.66")

        # When
        answer = _sign_in(alice, CHOSEN, forwarded_for="192.0.2.10")

    # Then
    assert throttled.status_code == 429
    assert SESSION_COOKIE not in attacker.cookies
    assert answer.status_code == 303
    assert SESSION_COOKIE in alice.cookies


def test_sign_in_without_csrf_token_is_refused(client: TestClient) -> None:
    # Given
    form = {"handle": "alice", "password": INITIAL}

    # When
    answer = client.post("/signin", data=form)

    # Then
    assert answer.status_code == 403
    assert SESSION_COOKIE not in client.cookies


def test_disabled_member_cannot_sign_in(client: TestClient, data_dir: Path) -> None:
    # Given
    with closing(serverdb.open_server_db(data_dir)) as conn:
        serverdb.disable_member(conn, "alice")

    # When
    answer = _sign_in(client, INITIAL)

    # Then
    assert answer.status_code == 400


def test_sign_out_ends_the_session(client: TestClient) -> None:
    # Given
    _sign_in(client, INITIAL)
    _change(client, CHOSEN, CHOSEN)

    # When
    client.post("/signout", data={"csrf": client.cookies[CSRF_COOKIE]})

    # Then
    page = client.get("/signin")
    assert 'name="password"' in page.text
    assert "Signed in as" not in page.text


def test_session_cookie_is_secure_http_only_and_same_site(client: TestClient) -> None:
    # Given
    client.get("/signin")

    # When
    answer = _sign_in(client, INITIAL)

    # Then
    cookie = next(
        value
        for value in answer.headers.get_list("set-cookie")
        if value.startswith(SESSION_COOKIE)
    ).lower()
    assert "secure" in cookie
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert "path=/" in cookie


def test_redirect_after_sign_in_stays_on_this_server(client: TestClient) -> None:
    # Given
    _sign_in(client, INITIAL)
    _change(client, CHOSEN, CHOSEN)
    client.cookies.delete(SESSION_COOKIE)

    # When
    answer = _sign_in(client, CHOSEN, next_path="//attacker.example/")

    # Then
    assert answer.headers["location"] == "/signin"


@pytest.mark.parametrize("path", ["/signin", "/oauth/authorize?consent=gone"])
def test_pages_set_a_strict_policy_and_load_nothing(
    client: TestClient, path: str
) -> None:
    # Given
    page_path = path

    # When
    page = client.get(page_path)

    # Then
    policy = page.headers["content-security-policy"]
    assert "default-src 'none'" in policy
    assert "frame-ancestors 'none'" in policy
    assert page.headers["cache-control"] == "no-store"
    for tag in ("<script", "<link", "<img", "<style", "<iframe", "style="):
        assert tag not in page.text
