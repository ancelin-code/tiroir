from collections.abc import Iterator
from contextlib import closing
from pathlib import Path

import httpx2  # the HTTP client of Starlette's TestClient
import pytest
from starlette.testclient import TestClient

from tiroir.core import serverdb
from tiroir.server.app import create_app
from tiroir.server.auth.sessions import CSRF_COOKIE, SESSION_COOKIE

ORIGIN = "https://testserver"
INITIAL = "initial-password"
CHOSEN = "my own long password"


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
    client: TestClient, password: str, handle: str = "alice", next_path: str = "/x"
) -> httpx2.Response:
    client.get("/signin")
    return client.post(
        "/signin",
        data={
            "csrf": client.cookies[CSRF_COOKIE],
            "handle": handle,
            "password": password,
            "next": next_path,
        },
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
