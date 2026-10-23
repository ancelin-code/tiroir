"""tiroir as the OAuth authorization server of its MCP endpoint (ADR-015).

The MCP SDK's handlers speak the protocol: request validation, PKCE (S256
only), redirect URI checks, client registration, token errors. This module is
the provider they call: registered clients, codes and tokens in `server.db`,
stored as digests; Client ID Metadata Documents fetched over HTTPS; and the
pending authorizations the consent page (`pages`) approves or denies.
"""

import asyncio
import base64
import binascii
import hmac
import ipaddress
import json
import re
import secrets
import socket
import sqlite3
import time
import uuid
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Iterator
from contextlib import closing, contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace
from pathlib import Path
from typing import override
from urllib.parse import unquote, urlencode, urlsplit

import httpx
from loguru import logger
from mcp.server.auth.handlers.metadata import (
    MetadataHandler,
    ProtectedResourceMetadataHandler,
)
from mcp.server.auth.handlers.register import RegistrationHandler
from mcp.server.auth.handlers.revoke import RevocationHandler
from mcp.server.auth.handlers.token import TokenHandler
from mcp.server.auth.middleware.client_auth import (
    AuthenticationError,
    ClientAuthenticator,
)
from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    AuthorizeError,
    OAuthAuthorizationServerProvider,
    RefreshToken,
    RegistrationError,
    TokenError,
    construct_redirect_uri,
)
from mcp.server.auth.settings import ClientRegistrationOptions
from mcp.server.transport_security import (
    DEFAULT_MAX_REQUEST_BODY_SIZE,
    RequestBodyLimitMiddleware,
)
from mcp.shared.auth import (
    OAuthClientInformationFull,
    OAuthMetadata,
    OAuthToken,
    ProtectedResourceMetadata,
)
from mcp.shared.inbound import MCP_PROTOCOL_VERSION_HEADER
from pydantic import ValidationError
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route, request_response
from starlette.types import ASGIApp, Receive, Scope, Send

from tiroir.core import serverdb
from tiroir.core.serverdb import (
    Member,
    OAuthCode,
    OAuthGrant,
    OAuthTokenHash,
    SpentSecret,
    open_server_db,
    secret_digest,
)
from tiroir.server.auth.sessions import SlidingWindow
from tiroir.server.auth.verify import (
    MCP_PATH,
    RESOURCE_METADATA_PATH,
    MemberTokenVerifier,
)

ACCESS_TOKEN_SECONDS = 3600
REFRESH_TOKEN_SECONDS = 30 * 24 * 3600  # unused for that long, a grant ends
CODE_SECONDS = 300
CONSENT_SECONDS = 600
MAX_PENDING = 1000
MAX_PENDING_PER_MEMBER = 10  # a member's oldest goes first, nobody else's

# Dynamic Client Registration: bounded per client, per address and in total.
MAX_REDIRECT_URIS = 10
REGISTRATIONS_PER_ADDRESS = 10
REGISTRATION_WINDOW_SECONDS = 3600
MAX_DCR_CLIENTS = 1000

AUTHORIZE_PATH = "/oauth/authorize"
CLIENT_AUTH_METHODS = ["none", "client_secret_post", "client_secret_basic"]

# Client ID Metadata Documents: small public JSON documents, fetched once.
DOCUMENT_MAX_BYTES = 5 * 1024
DOCUMENT_TIMEOUT_SECONDS = 5.0
DOCUMENT_CACHE_SECONDS = 3600
DOCUMENT_FAILURE_CACHE_SECONDS = 60
DOCUMENT_CACHE_SIZE = 256
DOCUMENT_PORT = 443
# Fetches of documents not in the cache, per client address: a client cannot
# make tiroir spend its time limit on new URLs without bound.
DOCUMENT_FETCHES_PER_ADDRESS = 10
DOCUMENT_FETCH_WINDOW_SECONDS = 60

type IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address
type Resolver = Callable[[str], Awaitable[list[IPAddress]]]

# IPv6 prefixes that carry an IPv4 address `is_global` does not look into.
_EMBEDDING_IPV4 = (
    ipaddress.IPv6Network("64:ff9b::/96"),  # NAT64
    ipaddress.IPv6Network("64:ff9b:1::/48"),  # local NAT64
)

# The address of the client whose request is being handled, set by `limited`.
_requester: ContextVar[str] = ContextVar("requester", default="")

# Redirect URIs a client may register (RFC 8252): a private-use scheme is a
# reverse domain name, such as `com.example.app`.
_PRIVATE_USE_SCHEME = re.compile(r"[a-z][a-z0-9+-]*(\.[a-z0-9][a-z0-9+-]*)+")
_LOOPBACK_HOSTS = ("127.0.0.1", "::1", "localhost")
_FORBIDDEN_SCHEMES = frozenset({"javascript", "data", "file", "vbscript", "blob"})


def metadata_document_url_valid(url: str) -> bool:
    """Whether `url` may name a client: HTTPS on 443, a path, no credentials or dots."""
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        return False
    segments = parts.path.split("/")
    return (
        parts.scheme == "https"
        and bool(parts.hostname)
        and port in (None, DOCUMENT_PORT)
        and parts.username is None
        and parts.password is None
        and not parts.fragment
        and parts.path not in ("", "/")
        and "." not in segments
        and ".." not in segments
    )


def redirect_uri_allowed(uri: str) -> bool:
    """Whether a client may use `uri`: https, loopback http or a private-use scheme.

    Loopback is `127.0.0.1`, `[::1]` or `localhost`, on any port. No redirect
    URI may carry a fragment.
    """
    try:
        parts = urlsplit(uri)
        _ = parts.port
    except ValueError:
        return False
    if "#" in uri or parts.scheme in _FORBIDDEN_SCHEMES:
        return False
    if parts.scheme == "https":
        return bool(parts.hostname)
    if parts.scheme == "http":
        return parts.hostname in _LOOPBACK_HOSTS
    return _PRIVATE_USE_SCHEME.fullmatch(parts.scheme) is not None


def address_public(address: IPAddress) -> bool:
    """Whether tiroir may connect to `address`: a global unicast address only.

    Refuses loopback, private, link-local, shared (CGNAT), multicast, reserved
    and unspecified addresses, and IPv6 addresses that embed an IPv4 one.
    """
    if isinstance(address, ipaddress.IPv6Address) and (
        address.ipv4_mapped is not None
        or address.sixtofour is not None
        or address.teredo is not None
        or any(address in network for network in _EMBEDDING_IPV4)
    ):
        return False
    return address.is_global and not (
        address.is_multicast
        or address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_unspecified
    )


async def resolve(host: str) -> list[IPAddress]:
    """The addresses `host` resolves to, through the system's resolver."""
    loop = asyncio.get_running_loop()
    infos = await loop.getaddrinfo(host, DOCUMENT_PORT, type=socket.SOCK_STREAM)
    return [ipaddress.ip_address(info[4][0]) for info in infos]


def client_from_document(url: str, body: bytes) -> OAuthClientInformationFull | None:
    """The public client a metadata document fetched from `url` describes."""
    try:
        document: object = json.loads(body)
    except ValueError:
        return None
    if not isinstance(document, dict) or document.get("client_id") != url:
        return None
    if "client_secret" in document or "client_secret_expires_at" in document:
        return None  # a document is public: it cannot hold a secret
    if document.get("token_endpoint_auth_method", "none") != "none":
        return None  # tiroir verifies no client key, so only public clients
    if not document.get("redirect_uris"):
        return None
    try:
        return OAuthClientInformationFull.model_validate(document)
    except ValidationError:
        return None


class ClientMetadataDocuments:
    """Clients named by the URL of their metadata document, fetched and cached."""

    def __init__(
        self,
        transport: httpx.AsyncBaseTransport | None = None,
        resolver: Resolver = resolve,
    ) -> None:
        self._transport = transport
        self._resolve = resolver
        self._cache: OrderedDict[
            str, tuple[float, OAuthClientInformationFull | None]
        ] = OrderedDict()
        self._fetches = SlidingWindow(
            DOCUMENT_FETCHES_PER_ADDRESS, DOCUMENT_FETCH_WINDOW_SECONDS
        )

    async def get(self, url: str) -> OAuthClientInformationFull | None:
        """The client `url` names, from the cache or fetched; `None` if refused."""
        now = time.monotonic()
        cached = self._cache.get(url)
        if cached is not None and cached[0] > now:
            return cached[1]
        if not metadata_document_url_valid(url):
            client = None
        else:
            requester = _requester.get()
            if self._fetches.full(requester):
                logger.warning("client metadata document fetches throttled")
                return None  # not cached: the document itself is not at fault
            self._fetches.record(requester)
            client = await self._fetch(url)
        lifetime = DOCUMENT_CACHE_SECONDS if client else DOCUMENT_FAILURE_CACHE_SECONDS
        self._cache[url] = (now + lifetime, client)
        self._cache.move_to_end(url)
        while len(self._cache) > DOCUMENT_CACHE_SIZE:
            self._cache.popitem(last=False)
        return client

    async def _fetch(self, url: str) -> OAuthClientInformationFull | None:
        try:
            async with asyncio.timeout(DOCUMENT_TIMEOUT_SECONDS):
                address = await self._public_address(urlsplit(url).hostname or "")
                body = None if address is None else await self._download(url, address)
        except (httpx.HTTPError, OSError, TimeoutError, ValueError):
            body = None
        client = None if body is None else client_from_document(url, body)
        if client is None:
            logger.warning("client metadata document refused: {}", url)
        return client

    async def _public_address(self, host: str) -> IPAddress | None:
        """The address to connect to for `host`, if every one it has is public."""
        try:
            addresses = [ipaddress.ip_address(host)]
        except ValueError:
            addresses = await self._resolve(host)
        if not addresses or not all(address_public(a) for a in addresses):
            return None
        return addresses[0]

    async def _download(self, url: str, address: IPAddress) -> bytes | None:
        # Connect to the address that was checked, so that a second resolution
        # cannot swap it; the name still goes in the Host header and in SNI,
        # against which the certificate is verified.
        host = urlsplit(url).hostname or ""
        target = httpx.URL(url).copy_with(host=str(address))
        async with (
            httpx.AsyncClient(
                transport=self._transport,
                follow_redirects=False,
                timeout=DOCUMENT_TIMEOUT_SECONDS,
                trust_env=False,
            ) as http,
            http.stream(
                "GET",
                target,
                headers={"Accept": "application/json", "Host": host},
                extensions={"sni_hostname": host},
            ) as answer,
        ):
            if answer.status_code != 200:
                return None
            body = bytearray()
            async for chunk in answer.aiter_bytes():
                body.extend(chunk)
                if len(body) > DOCUMENT_MAX_BYTES:
                    return None
            return bytes(body)


@dataclass(frozen=True)
class PendingAuthorization:
    """A validated authorization request waiting for the member's consent."""

    client: OAuthClientInformationFull
    params: AuthorizationParams
    expires: float
    member: str  # the id of the member who asked, the only one who may answer


@dataclass(frozen=True)
class Authorizing:
    """Who asks the authorization endpoint, for `TiroirProvider.authorize`."""

    member: Member | None  # signed in, with a password of their own
    signin_url: str  # where to sign in, coming back to the same request


_authorizing: ContextVar[Authorizing | None] = ContextVar("authorizing", default=None)


@contextmanager
def authorizing(asking: Authorizing) -> Iterator[None]:
    """Make who asks known to the provider while the SDK handles the request."""
    token = _authorizing.set(asking)
    try:
        yield
    finally:
        _authorizing.reset(token)


def _spent_until() -> int:
    """How long an exchanged code or refresh token is remembered: a grant's life."""
    return int(time.time()) + REFRESH_TOKEN_SECONDS


def _new_tokens(scopes: tuple[str, ...]) -> tuple[OAuthToken, list[OAuthTokenHash]]:
    now = int(time.time())
    access = "tir_at_" + secrets.token_urlsafe(32)
    refresh = "tir_rt_" + secrets.token_urlsafe(32)
    token = OAuthToken(
        access_token=access,
        expires_in=ACCESS_TOKEN_SECONDS,
        refresh_token=refresh,
        scope=" ".join(scopes) or None,
    )
    return token, [
        OAuthTokenHash(secret_digest(access), "access", now + ACCESS_TOKEN_SECONDS),
        OAuthTokenHash(secret_digest(refresh), "refresh", now + REFRESH_TOKEN_SECONDS),
    ]


class TiroirProvider(
    OAuthAuthorizationServerProvider[AuthorizationCode, RefreshToken, AccessToken]
):
    """The MCP SDK's authorization server provider, backed by `server.db`."""

    def __init__(
        self, data_dir: Path, origin: str, documents: ClientMetadataDocuments
    ) -> None:
        self.data_dir = data_dir
        self.origin = origin
        self.resource = origin + MCP_PATH
        self.documents = documents
        self.verifier = MemberTokenVerifier(data_dir)
        self._pending: OrderedDict[str, PendingAuthorization] = OrderedDict()

    def connect(self) -> closing[sqlite3.Connection]:
        return closing(open_server_db(self.data_dir))

    @override
    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        if client_id.startswith("https://"):
            return await self.documents.get(client_id)
        with self.connect() as conn:
            found = serverdb.oauth_client(conn, client_id)
        if found is None:
            return None
        return OAuthClientInformationFull.model_validate_json(found[0])

    def client_secret_hash(self, client_id: str) -> str | None:
        with self.connect() as conn:
            found = serverdb.oauth_client(conn, client_id)
        return None if found is None else found[1]

    @override
    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        """Store a client, unless a redirect URI is unsafe or there are too many.

        Raises `serverdb.ClientStoreFull` when no stored client can make room.
        """
        uris = [str(uri) for uri in client_info.redirect_uris or ()]
        if len(uris) > MAX_REDIRECT_URIS:
            raise RegistrationError(
                "invalid_redirect_uri", f"at most {MAX_REDIRECT_URIS} redirect URIs"
            )
        if not all(redirect_uri_allowed(uri) for uri in uris):
            raise RegistrationError(
                "invalid_redirect_uri",
                "a redirect URI is https, loopback http or a private-use scheme"
                " (RFC 8252), without fragment",
            )
        secret = client_info.client_secret
        metadata = client_info.model_dump_json(
            exclude={"client_secret"}, exclude_none=True
        )
        with self.connect() as conn:
            serverdb.save_oauth_client(
                conn,
                client_info.client_id,
                metadata,
                None if secret is None else secret_digest(secret),
                limit=MAX_DCR_CLIENTS,
            )
        logger.info("oauth client registered: {}", client_info.client_id)

    @override
    async def authorize(
        self, client: OAuthClientInformationFull, params: AuthorizationParams
    ) -> str:
        # Every token is bound to the MCP endpoint, the only resource here.
        if params.resource is not None and params.resource.rstrip("/") != self.resource:
            raise AuthorizeError("invalid_target", "unknown resource")
        params = params.model_copy(update={"resource": self.resource})
        asking = _authorizing.get()
        if asking is None:
            raise AuthorizeError("access_denied", "no member to ask")
        if asking.member is None:
            # Nothing is kept for an anonymous request: sign-in comes back to it.
            return asking.signin_url
        member_id = asking.member.id
        now = time.monotonic()
        while self._pending and next(iter(self._pending.values())).expires < now:
            self._pending.popitem(last=False)
        mine = [key for key, p in self._pending.items() if p.member == member_id]
        for key in mine[: max(0, len(mine) - MAX_PENDING_PER_MEMBER + 1)]:
            del self._pending[key]
        if len(self._pending) >= MAX_PENDING:
            logger.warning("pending authorizations full, request refused")
            raise AuthorizeError("temporarily_unavailable", "try again later")
        consent_id = secrets.token_urlsafe(32)
        self._pending[consent_id] = PendingAuthorization(
            client, params, now + CONSENT_SECONDS, member_id
        )
        return f"{self.origin}{AUTHORIZE_PATH}?{urlencode({'consent': consent_id})}"

    def pending(self, consent_id: str) -> PendingAuthorization | None:
        pending = self._pending.get(consent_id)
        if pending is None or pending.expires < time.monotonic():
            return None
        return pending

    def _redirect(self, pending: PendingAuthorization, **values: str | None) -> str:
        return construct_redirect_uri(
            str(pending.params.redirect_uri),
            **values,
            state=pending.params.state,
            iss=self.origin,  # RFC 9207
        )

    def approve(self, consent_id: str, member: Member) -> str | None:
        """Issue the code of a pending authorization; where to send the browser."""
        pending = self.pending(consent_id)
        if pending is None:
            return None
        del self._pending[consent_id]
        params = pending.params
        code = secrets.token_urlsafe(32)
        with self.connect() as conn:
            serverdb.save_oauth_code(
                conn,
                secret_digest(code),
                OAuthCode(
                    client_id=pending.client.client_id,
                    member=member.id,
                    scopes=tuple(params.scopes or ()),
                    code_challenge=params.code_challenge,
                    redirect_uri=str(params.redirect_uri),
                    redirect_uri_explicit=params.redirect_uri_provided_explicitly,
                    resource=params.resource,
                    expires=time.time() + CODE_SECONDS,
                ),
            )
        logger.info("authorization approved by member {}", member.id)
        return self._redirect(pending, code=code)

    def deny(self, consent_id: str) -> str | None:
        pending = self.pending(consent_id)
        if pending is None:
            return None
        del self._pending[consent_id]
        return self._redirect(pending, error="access_denied")

    @override
    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AuthorizationCode | None:
        code_hash = secret_digest(authorization_code)
        with self.connect() as conn:
            found = serverdb.oauth_code(conn, code_hash)
            if found is None:
                serverdb.revoke_reused_secret(conn, code_hash, "code", time.time())
        if found is None or found.client_id != client.client_id:
            return None
        return AuthorizationCode.model_validate(
            {
                "code": authorization_code,
                "scopes": list(found.scopes),
                "expires_at": found.expires,
                "client_id": found.client_id,
                "code_challenge": found.code_challenge,
                "redirect_uri": found.redirect_uri,
                "redirect_uri_provided_explicitly": found.redirect_uri_explicit,
                "resource": found.resource,
                "subject": found.member,
            }
        )

    @override
    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> OAuthToken:
        code_hash = secret_digest(authorization_code.code)
        with self.connect() as conn:
            if not serverdb.consume_oauth_code(conn, code_hash):
                serverdb.revoke_reused_secret(conn, code_hash, "code", time.time())
                raise TokenError("invalid_grant", "authorization code already used")
            member = serverdb.active_member(conn, authorization_code.subject or "")
            if member is None:
                raise TokenError("invalid_grant", "member disabled")
            grant = OAuthGrant(
                grant_id=uuid.uuid4().hex,
                client_id=client.client_id,
                member=member.id,
                scopes=tuple(authorization_code.scopes),
                resource=authorization_code.resource,
            )
            token, hashes = _new_tokens(grant.scopes)
            spent = SpentSecret(code_hash, "code", _spent_until())
            serverdb.save_oauth_tokens(conn, grant, hashes, spent)
        return token

    @override
    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> RefreshToken | None:
        token_hash = secret_digest(refresh_token)
        now = time.time()
        with self.connect() as conn:
            found = serverdb.oauth_token(conn, token_hash, "refresh", now)
            if found is None:
                serverdb.revoke_reused_secret(conn, token_hash, "refresh", now)
        if found is None or found[0].client_id != client.client_id:
            return None
        grant, expires = found
        return RefreshToken(
            token=refresh_token,
            client_id=grant.client_id,
            scopes=list(grant.scopes),
            expires_at=expires,
            resource=grant.resource,
            subject=grant.member,
        )

    @override
    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: RefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        old_hash = secret_digest(refresh_token.token)
        with self.connect() as conn:
            found = serverdb.oauth_token(conn, old_hash, "refresh", time.time())
            if found is None:
                raise TokenError("invalid_grant", "refresh token does not exist")
            grant = replace(found[0], scopes=tuple(scopes))
            if serverdb.active_member(conn, grant.member) is None:
                raise TokenError("invalid_grant", "member disabled")
            token, hashes = _new_tokens(grant.scopes)
            if not serverdb.rotate_refresh_token(
                conn, old_hash, grant, hashes, _spent_until()
            ):
                serverdb.revoke_reused_secret(conn, old_hash, "refresh", time.time())
                raise TokenError("invalid_grant", "refresh token already used")
        return token

    @override
    async def load_access_token(self, token: str) -> AccessToken | None:
        return await self.verifier.verify_token(token)

    @override
    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        with self.connect() as conn:
            serverdb.revoke_oauth_grant(conn, secret_digest(token.token))


def _basic_secret(header: str, client_id: str) -> str | None:
    if not header.startswith("Basic "):
        return None
    try:
        decoded = base64.b64decode(header[6:], validate=True).decode()
    except (binascii.Error, UnicodeDecodeError):
        return None
    basic_id, sep, secret = decoded.partition(":")
    if not sep or unquote(basic_id) != client_id:
        return None
    return unquote(secret)


class HashedSecretAuthenticator(ClientAuthenticator):
    """The SDK's client authentication, against a secret stored as a digest."""

    def __init__(self, provider: TiroirProvider) -> None:
        super().__init__(provider)
        self.tiroir = provider

    @override
    async def authenticate_request(
        self, request: Request
    ) -> OAuthClientInformationFull:
        form = await request.form()
        client_id = form.get("client_id")
        if not isinstance(client_id, str) or not client_id:
            raise AuthenticationError("Missing client_id")
        client = await self.tiroir.get_client(client_id)
        if client is None:
            raise AuthenticationError("Invalid client_id")
        method = client.token_endpoint_auth_method or "none"
        if method == "none":
            return client
        if method == "client_secret_basic":
            secret = _basic_secret(request.headers.get("Authorization", ""), client_id)
        elif method == "client_secret_post":
            posted = form.get("client_secret")
            secret = posted if isinstance(posted, str) else None
        else:
            raise AuthenticationError(f"Unsupported auth method: {method}")
        stored = self.tiroir.client_secret_hash(client_id)
        if (
            not secret
            or stored is None
            or not hmac.compare_digest(stored, secret_digest(secret))
        ):
            raise AuthenticationError("Invalid client_secret")
        return client


class RecordRequester:
    """Make the client's address known to the fetches of metadata documents."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        client = scope.get("client")
        token = _requester.set(client[0] if client else "")
        try:
            await self.app(scope, receive, send)
        finally:
            _requester.reset(token)


def limited(handler: Callable[[Request], Awaitable[Response]]) -> ASGIApp:
    """An endpoint whose request body is capped, as the SDK caps its own.

    It also records the client's address, which limits its document fetches.
    """
    return RecordRequester(
        RequestBodyLimitMiddleware(
            request_response(handler), DEFAULT_MAX_REQUEST_BODY_SIZE
        )
    )


class Registration:
    """The SDK's client registration, limited per client address and in total."""

    def __init__(self, provider: TiroirProvider) -> None:
        self.sdk = RegistrationHandler(
            provider, ClientRegistrationOptions(enabled=True)
        )
        self.attempts = SlidingWindow(
            REGISTRATIONS_PER_ADDRESS, REGISTRATION_WINDOW_SECONDS
        )

    async def handle(self, request: Request) -> Response:
        """Register a client; 429 for an address over its limit, 503 when full."""
        requester = _requester.get()
        if self.attempts.full(requester):
            logger.warning("client registrations throttled")
            return _unavailable(429, "too many registrations, try again later")
        self.attempts.record(requester)
        try:
            return await self.sdk.handle(request)
        except serverdb.ClientStoreFull:
            logger.error("client registrations are full: no idle client to forget")
            return _unavailable(503, "no room for a new client, try again later")


def _unavailable(status: int, description: str) -> Response:
    return JSONResponse(
        {"error": "temporarily_unavailable", "error_description": description},
        status,
        headers={"Cache-Control": "no-store"},
    )


def _client_endpoint(
    handler: Callable[[Request], Awaitable[Response]], methods: list[str]
) -> ASGIApp:
    # Clients running in a browser (MCP Inspector) call these across origins.
    return CORSMiddleware(
        limited(handler),
        allow_origins=["*"],
        allow_methods=methods,
        allow_headers=[MCP_PROTOCOL_VERSION_HEADER],
    )


def oauth_routes(provider: TiroirProvider) -> list[Route]:
    """The metadata, token, registration and revocation endpoints.

    The authorization endpoint, which needs a signed-in member, is in `pages`.
    """
    origin = provider.origin
    metadata = OAuthMetadata.model_validate(
        {
            "issuer": origin,
            "authorization_endpoint": origin + AUTHORIZE_PATH,
            "token_endpoint": f"{origin}/oauth/token",
            "registration_endpoint": f"{origin}/oauth/register",
            "revocation_endpoint": f"{origin}/oauth/revoke",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "token_endpoint_auth_methods_supported": CLIENT_AUTH_METHODS,
            "revocation_endpoint_auth_methods_supported": CLIENT_AUTH_METHODS,
            "code_challenge_methods_supported": ["S256"],
            "client_id_metadata_document_supported": True,
            "authorization_response_iss_parameter_supported": True,
        }
    )
    resource = ProtectedResourceMetadata.model_validate(
        {"resource": provider.resource, "authorization_servers": [origin]}
    )
    authenticator = HashedSecretAuthenticator(provider)
    registration = Registration(provider)
    read, write = ["GET", "OPTIONS"], ["POST", "OPTIONS"]
    return [
        Route(
            "/.well-known/oauth-authorization-server",
            _client_endpoint(MetadataHandler(metadata).handle, read),
            methods=read,
        ),
        Route(
            RESOURCE_METADATA_PATH,
            _client_endpoint(ProtectedResourceMetadataHandler(resource).handle, read),
            methods=read,
        ),
        Route(
            "/oauth/token",
            _client_endpoint(TokenHandler(provider, authenticator).handle, write),
            methods=write,
        ),
        Route(
            "/oauth/register",
            _client_endpoint(registration.handle, write),
            methods=write,
        ),
        Route(
            "/oauth/revoke",
            _client_endpoint(RevocationHandler(provider, authenticator).handle, write),
            methods=write,
        ),
    ]
