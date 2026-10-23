"""The sign-in, password change and consent pages (ADR-015).

Plain HTML from `templates/`, no script, style or third-party resource, under
a strict Content-Security-Policy. The authorization endpoint lives here: the
SDK validates a client's request, then the member signs in and consents.
"""

import re
from typing import Any
from urllib.parse import urlencode, urlsplit

from jinja2 import Environment, PackageLoader
from loguru import logger
from mcp.server.auth.handlers.authorize import AuthorizationHandler
from starlette.datastructures import FormData
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response
from starlette.routing import Route
from starlette.templating import Jinja2Templates

from tiroir.core import serverdb
from tiroir.server.auth.oauth import (
    AUTHORIZE_PATH,
    PendingAuthorization,
    TiroirProvider,
    limited,
)
from tiroir.server.auth.sessions import (
    SignInThrottle,
    csrf_token,
    csrf_valid,
    end_session,
    session_member,
    set_csrf_cookie,
    start_session,
)

MIN_PASSWORD_LENGTH = 12
SIGNIN_PATH = "/signin"

_templates = Jinja2Templates(
    env=Environment(loader=PackageLoader("tiroir.server", "templates"), autoescape=True)
)
_SOURCE = re.compile(r"[a-z][a-z0-9+.-]*:(//[A-Za-z0-9.:\[\]-]+)?")


def _form_target(redirect_uri: str) -> str:
    """The CSP source of a client's redirect URI, where consent sends the browser.

    Browsers apply `form-action` to the redirect that follows a form, so the
    consent page must allow it; anything unexpected allows nothing more.
    """
    parts = urlsplit(redirect_uri)
    source = f"{parts.scheme}://{parts.netloc}" if parts.netloc else f"{parts.scheme}:"
    return f" {source}" if _SOURCE.fullmatch(source) else ""


def safe_next(value: object) -> str:
    """A local path to return to after signing in; anything else is ignored."""
    if (
        isinstance(value, str)
        and value.startswith("/")
        and not value.startswith("//")
        and "\\" not in value
    ):
        return value
    return SIGNIN_PATH


def _signin_redirect(next_path: str) -> Response:
    return RedirectResponse(f"{SIGNIN_PATH}?{urlencode({'next': next_path})}", 303)


def _page(
    request: Request,
    name: str,
    context: dict[str, Any],
    status: int = 200,
    form_target: str = "",
) -> Response:
    csrf = csrf_token(request)
    response = _templates.TemplateResponse(
        request, name, {**context, "csrf": csrf}, status_code=status
    )
    set_csrf_cookie(response, csrf)
    response.headers.update(
        {
            "Content-Security-Policy": (
                f"default-src 'none'; form-action 'self'{form_target};"
                " frame-ancestors 'none'; base-uri 'none'"
            ),
            "Cache-Control": "no-store",
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
        }
    )
    return response


class Pages:
    def __init__(self, provider: TiroirProvider, throttle: SignInThrottle) -> None:
        self.provider = provider
        self.data_dir = provider.data_dir
        self.throttle = throttle
        self.sdk_authorize = AuthorizationHandler(provider)

    async def signin(self, request: Request) -> Response:
        if request.method == "GET":
            next_path = safe_next(request.query_params.get("next"))
            member = session_member(request, self.data_dir)
            if member is not None and member.must_change_password:
                return _page(request, "change_password.html", {"next": next_path})
            if member is not None and "next" in request.query_params:
                return RedirectResponse(next_path, 303)
            return _page(request, "signin.html", {"member": member, "next": next_path})
        form = await request.form()
        next_path = safe_next(form.get("next"))
        if not csrf_valid(request, form.get("csrf")):
            error = "This form has expired. Please try again."
            return _page(
                request, "signin.html", {"next": next_path, "error": error}, 403
            )
        if "new_password" in form:
            return self._change_password(request, form, next_path)
        return self._sign_in(request, form, next_path)

    def _sign_in(self, request: Request, form: FormData, next_path: str) -> Response:
        handle = str(form.get("handle", "")).strip()
        password = str(form.get("password", ""))
        address = request.client.host if request.client else ""
        if self.throttle.blocked(handle, address):
            logger.warning("sign-in throttled")
            error = "Too many failed sign-ins. Wait a minute, then try again."
            return _page(
                request, "signin.html", {"next": next_path, "error": error}, 429
            )
        with self.provider.connect() as conn:
            member = serverdb.authenticate(conn, handle, password)
        if member is None:
            self.throttle.failed(handle, address)
            logger.info("sign-in failed")
            error = "Unknown handle or wrong password."
            return _page(
                request, "signin.html", {"next": next_path, "error": error}, 400
            )
        if member.must_change_password:
            response = _signin_redirect(next_path)
        else:
            response = RedirectResponse(next_path, 303)
        start_session(request, response, self.data_dir, member)
        logger.info("member signed in: {}", member.id)
        return response

    def _change_password(
        self, request: Request, form: FormData, next_path: str
    ) -> Response:
        # Only the change forced at first sign-in; a chosen password changes on
        # the account page, which asks for the current one.
        member = session_member(request, self.data_dir)
        if member is None or not member.must_change_password:
            return _signin_redirect(next_path)
        password = str(form.get("new_password", ""))
        with self.provider.connect() as conn:
            if len(password) < MIN_PASSWORD_LENGTH:
                error = f"Choose at least {MIN_PASSWORD_LENGTH} characters."
            elif password != str(form.get("confirm_password", "")):
                error = "The two passwords differ."
            elif serverdb.authenticate(conn, member.handle, password) is not None:
                error = "Choose a password other than the one you were given."
            else:
                serverdb.change_password(conn, member.id, password)
                return RedirectResponse(next_path, 303)
        return _page(
            request,
            "change_password.html",
            {"next": next_path, "error": error},
            400,
        )

    async def signout(self, request: Request) -> Response:
        response = RedirectResponse(SIGNIN_PATH, 303)
        if request.method == "POST":
            form = await request.form()
            if csrf_valid(request, form.get("csrf")):
                end_session(request, response, self.data_dir)
        return response

    async def authorize(self, request: Request) -> Response:
        """The authorization endpoint: the SDK's checks, then sign-in and consent."""
        if request.method == "GET":
            form = None
            consent_id = request.query_params.get("consent")
        else:
            form = await request.form()
            consent_id = form.get("consent")
        if not isinstance(consent_id, str):
            return await self.sdk_authorize.handle(request)
        pending = self.provider.pending(consent_id)
        if pending is None:
            return _page(request, "consent.html", {"expired": True}, 400)
        member = session_member(request, self.data_dir)
        if member is None or member.must_change_password:
            return _signin_redirect(
                f"{AUTHORIZE_PATH}?{urlencode({'consent': consent_id})}"
            )
        if form is None:
            return self._consent_page(request, pending, consent_id, member)
        if not csrf_valid(request, form.get("csrf")):
            return self._consent_page(request, pending, consent_id, member, 403)
        if form.get("decision") == "approve":
            target = self.provider.approve(consent_id, member)
        else:
            target = self.provider.deny(consent_id)
        if target is None:
            return _page(request, "consent.html", {"expired": True}, 400)
        return RedirectResponse(target, 303)

    def _consent_page(
        self,
        request: Request,
        pending: PendingAuthorization,
        consent_id: str,
        member: serverdb.Member,
        status: int = 200,
    ) -> Response:
        client = pending.client
        redirect_uri = str(pending.params.redirect_uri)
        context = {
            "consent": consent_id,
            "member": member,
            "client_name": client.client_name or "An application",
            "client_id": client.client_id,
            "redirect_host": urlsplit(redirect_uri).netloc or redirect_uri,
            "error": None if status == 200 else "This form has expired. Try again.",
        }
        return _page(
            request, "consent.html", context, status, _form_target(redirect_uri)
        )


def page_routes(provider: TiroirProvider) -> list[Route]:
    pages = Pages(provider, SignInThrottle())
    methods = ["GET", "POST"]
    return [
        Route(AUTHORIZE_PATH, limited(pages.authorize), methods=methods),
        Route(SIGNIN_PATH, limited(pages.signin), methods=methods),
        Route("/signout", limited(pages.signout), methods=methods),
    ]
