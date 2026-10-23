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
from collections.abc import Callable, Hashable
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
FAILURES_PER_HANDLE = 10  # from one address
FAILURES_PER_ADDRESS = 30
HANDLE_DELAY_STEP_SECONDS = 0.25
HANDLE_DELAY_MAX_SECONDS = 5.0


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
        self._events: dict[Hashable, deque[float]] = {}

    def _recent(self, key: Hashable) -> deque[float]:
        events = self._events.get(key, deque[float]())
        horizon = self.clock() - self.seconds
        while events and events[0] <= horizon:
            events.popleft()
        if not events:
            self._events.pop(key, None)
        return events

    def count(self, key: Hashable) -> int:
        return len(self._recent(key))

    def full(self, key: Hashable) -> bool:
        return self.count(key) >= self.limit

    def record(self, key: Hashable) -> None:
        events = self._recent(key)
        events.append(self.clock())
        self._events[key] = events
        if len(self._events) > 10_000:  # forget the keys gone quiet
            for stale in list(self._events):
                self._recent(stale)


class SignInThrottle:
    """Refuse an address after repeated failures; slow down a handle under attack.

    An address is refused after 10 failures on one handle, or 30 in all, within
    a minute. Failures on a handle from every address together only delay its
    sign-ins, so that nobody can lock a member out by failing on purpose.
    """

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self.attempts = SlidingWindow(FAILURES_PER_HANDLE, THROTTLE_SECONDS, clock)
        self.addresses = SlidingWindow(FAILURES_PER_ADDRESS, THROTTLE_SECONDS, clock)
        self.handles = SlidingWindow(FAILURES_PER_HANDLE, THROTTLE_SECONDS, clock)

    def blocked(self, handle: str, address: str) -> bool:
        return self.attempts.full((handle, address)) or self.addresses.full(address)

    def delay(self, handle: str) -> float:
        """Seconds to wait before checking a password for `handle`."""
        excess = self.handles.count(handle) - FAILURES_PER_HANDLE + 1
        if excess <= 0:
            return 0.0
        return min(HANDLE_DELAY_MAX_SECONDS, HANDLE_DELAY_STEP_SECONDS * excess)

    def failed(self, handle: str, address: str) -> None:
        self.attempts.record((handle, address))
        self.addresses.record(address)
        self.handles.record(handle)
