"""Web sessions, CSRF tokens and sign-in throttling (ADR-015).

Both cookies are secure, HTTP-only and same-site (`Lax`, so that a client's
redirect to the authorization endpoint still carries the session), with the
`__Host-` prefix that keeps other hosts from setting them. A form carries the
CSRF cookie's value back in a hidden field (double submit).
"""

import hmac
import secrets
import time
from collections import deque
from collections.abc import Callable
from contextlib import closing
from pathlib import Path

from starlette.requests import Request
from starlette.responses import Response

from tiroir.core import serverdb
from tiroir.core.serverdb import Member, open_server_db, secret_digest

SESSION_COOKIE = "__Host-tiroir_session"
CSRF_COOKIE = "__Host-tiroir_csrf"
SESSION_SECONDS = 12 * 3600

THROTTLE_SECONDS = 60
FAILURES_PER_HANDLE = 10
FAILURES_PER_ADDRESS = 30


def _set_cookie(response: Response, name: str, value: str) -> None:
    response.set_cookie(
        name,
        value,
        max_age=SESSION_SECONDS,
        path="/",
        secure=True,
        httponly=True,
        samesite="lax",
    )


def session_member(request: Request, data_dir: Path) -> Member | None:
    """The active member signed in on this browser, or `None`."""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    with closing(open_server_db(data_dir)) as conn:
        member = serverdb.web_session_member(conn, secret_digest(token), time.time())
    if member is not None:
        request.state.member_handle = member.handle  # for the request log
    return member


def start_session(
    request: Request, response: Response, data_dir: Path, member: Member
) -> None:
    """Sign the member in, on a new session that replaces this browser's."""
    token = secrets.token_urlsafe(32)
    with closing(open_server_db(data_dir)) as conn:
        previous = request.cookies.get(SESSION_COOKIE)
        if previous:
            serverdb.delete_web_session(conn, secret_digest(previous))
        serverdb.create_web_session(
            conn, secret_digest(token), member.id, int(time.time()) + SESSION_SECONDS
        )
    _set_cookie(response, SESSION_COOKIE, token)


def end_session(request: Request, response: Response, data_dir: Path) -> None:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        with closing(open_server_db(data_dir)) as conn:
            serverdb.delete_web_session(conn, secret_digest(token))
    response.delete_cookie(
        SESSION_COOKIE, path="/", secure=True, httponly=True, samesite="lax"
    )


def csrf_token(request: Request) -> str:
    """This browser's CSRF token; a new one goes out with `set_csrf_cookie`."""
    return request.cookies.get(CSRF_COOKIE) or secrets.token_urlsafe(32)


def set_csrf_cookie(response: Response, token: str) -> None:
    _set_cookie(response, CSRF_COOKIE, token)


def csrf_valid(request: Request, submitted: object) -> bool:
    expected = request.cookies.get(CSRF_COOKIE)
    return (
        bool(expected)
        and isinstance(submitted, str)
        and hmac.compare_digest(expected.encode(), submitted.encode())
    )


class SlidingWindow:
    """Count events per key over the last `seconds`."""

    def __init__(
        self, limit: int, seconds: float, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self.limit = limit
        self.seconds = seconds
        self.clock = clock
        self._events: dict[str, deque[float]] = {}

    def _recent(self, key: str) -> deque[float]:
        events = self._events.get(key, deque[float]())
        horizon = self.clock() - self.seconds
        while events and events[0] <= horizon:
            events.popleft()
        if not events:
            self._events.pop(key, None)
        return events

    def full(self, key: str) -> bool:
        return len(self._recent(key)) >= self.limit

    def record(self, key: str) -> None:
        events = self._recent(key)
        events.append(self.clock())
        self._events[key] = events
        if len(self._events) > 10_000:  # forget the keys gone quiet
            for stale in list(self._events):
                self._recent(stale)


class SignInThrottle:
    """Refuse sign-ins after repeated failures, per handle and per address."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self.handles = SlidingWindow(FAILURES_PER_HANDLE, THROTTLE_SECONDS, clock)
        self.addresses = SlidingWindow(FAILURES_PER_ADDRESS, THROTTLE_SECONDS, clock)

    def blocked(self, handle: str, address: str) -> bool:
        return self.handles.full(handle) or self.addresses.full(address)

    def failed(self, handle: str, address: str) -> None:
        self.handles.record(handle)
        self.addresses.record(address)
