import asyncio
import ipaddress
import json
from pathlib import Path

import httpx
import pytest
from mcp.shared.auth import OAuthClientInformationFull
from starlette.testclient import TestClient

from tiroir.server.app import create_app
from tiroir.server.auth.oauth import (
    DOCUMENT_FETCHES_PER_ADDRESS,
    DOCUMENT_MAX_BYTES,
    ClientMetadataDocuments,
    IPAddress,
    Resolver,
)

URL = "https://client.example/oauth/client.json"
PUBLIC = "93.184.215.14"
REDIRECT_URI = "http://127.0.0.1:33418/callback"
DOCUMENT = {
    "client_id": URL,
    "client_name": "Test Client",
    "redirect_uris": [REDIRECT_URI],
    "token_endpoint_auth_method": "none",
}


def _serving(
    answer: httpx.Response | Exception, requests: list[httpx.Request] | None = None
) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if requests is not None:
            requests.append(request)
        if isinstance(answer, Exception):
            raise answer
        return answer

    return httpx.MockTransport(handler)


def _resolving(*answers: str, asked: list[str] | None = None) -> Resolver:
    """A resolver giving each answer in turn, the last one ever after."""
    remaining = list(answers)

    async def resolver(host: str) -> list[IPAddress]:
        if asked is not None:
            asked.append(host)
        answer = remaining.pop(0) if len(remaining) > 1 else remaining[0]
        return [ipaddress.ip_address(answer)]

    return resolver


def test_document_is_fetched_once_then_cached() -> None:
    # Given
    requests: list[httpx.Request] = []
    documents = ClientMetadataDocuments(
        _serving(httpx.Response(200, json=DOCUMENT), requests), _resolving(PUBLIC)
    )

    async def twice() -> list[OAuthClientInformationFull | None]:
        return [await documents.get(URL), await documents.get(URL)]

    # When
    clients = asyncio.run(twice())

    # Then
    assert len(requests) == 1
    assert requests[0].url == f"https://{PUBLIC}/oauth/client.json"
    assert requests[0].headers["Host"] == "client.example"
    assert requests[0].extensions["sni_hostname"] == "client.example"
    first = clients[0]
    assert first is not None and first is clients[1]
    assert first.client_name == "Test Client"


@pytest.mark.parametrize(
    "url",
    [
        "http://client.example/oauth/client.json",
        "https://client.example/",
        "https://user:pass@client.example/client.json",
        "https://client.example/a/../client.json",
        "https://client.example/client.json#frag",
        "https://client.example:8443/client.json",
    ],
)
def test_url_that_cannot_name_a_client_is_not_fetched(url: str) -> None:
    # Given
    requests: list[httpx.Request] = []
    documents = ClientMetadataDocuments(
        _serving(httpx.Response(200, json=DOCUMENT), requests), _resolving(PUBLIC)
    )

    # When
    client = asyncio.run(documents.get(url))

    # Then
    assert client is None
    assert requests == []


@pytest.mark.parametrize(
    "answer",
    [
        httpx.Response(404),
        httpx.Response(302, headers={"Location": "https://elsewhere.example/c"}),
        httpx.Response(200, json={**DOCUMENT, "client_id": "https://other.example/c"}),
        httpx.Response(200, json={**DOCUMENT, "client_secret": "s"}),
        httpx.Response(
            200, json={**DOCUMENT, "token_endpoint_auth_method": "client_secret_post"}
        ),
        httpx.Response(200, json={**DOCUMENT, "redirect_uris": []}),
        httpx.Response(200, content=b"not json"),
        httpx.Response(
            200,
            content=json.dumps(
                {**DOCUMENT, "padding": "x" * DOCUMENT_MAX_BYTES}
            ).encode(),
        ),
        httpx.ConnectError("unreachable"),
        httpx.ReadTimeout("too slow"),
    ],
)
def test_unusable_document_is_refused(answer: httpx.Response | Exception) -> None:
    # Given
    documents = ClientMetadataDocuments(_serving(answer), _resolving(PUBLIC))

    # When
    client = asyncio.run(documents.get(URL))

    # Then
    assert client is None


def test_slow_document_is_abandoned_after_the_time_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given
    monkeypatch.setattr("tiroir.server.auth.oauth.DOCUMENT_TIMEOUT_SECONDS", 0.05)

    async def slow(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(1)
        return httpx.Response(200, json=DOCUMENT)

    documents = ClientMetadataDocuments(httpx.MockTransport(slow), _resolving(PUBLIC))

    # When
    client = asyncio.run(documents.get(URL))

    # Then
    assert client is None


def test_authorization_by_unreachable_document_is_refused(tmp_path: Path) -> None:
    # Given
    app = create_app(
        tmp_path,
        origin="https://testserver",
        http_transport=_serving(httpx.ConnectError("unreachable")),
        resolver=_resolving(PUBLIC),
    )
    params = {
        "response_type": "code",
        "client_id": URL,
        "redirect_uri": REDIRECT_URI,
        "code_challenge": "x" * 43,
        "code_challenge_method": "S256",
    }

    # When
    with TestClient(app, base_url="https://testserver") as client:
        answer = client.get("/oauth/authorize", params=params, follow_redirects=False)

    # Then
    assert answer.status_code == 400
    assert answer.json()["error"] == "invalid_request"


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1/x",
        "https://127.1/x",
        "https://169.254.169.254/x",
        "https://10.0.0.1/x",
        "https://172.16.0.1/x",
        "https://192.168.1.1/x",
        "https://100.64.0.1/x",
        "https://224.0.0.1/x",
        "https://0.0.0.0/x",
        "https://[::1]/x",
        "https://[::]/x",
        "https://[fe80::1]/x",
        "https://[fc00::1]/x",
        "https://[ff02::1]/x",
        "https://[::ffff:127.0.0.1]/x",
        "https://[::ffff:8.8.8.8]/x",
        "https://[64:ff9b::7f00:1]/x",
        "https://[2002:7f00:1::1]/x",
    ],
)
def test_address_that_is_not_public_is_never_connected_to(url: str) -> None:
    # Given
    requests: list[httpx.Request] = []

    async def resolver(host: str) -> list[IPAddress]:
        # The system's resolver reads `127.1` as 127.0.0.1; the others are
        # literal addresses, which are never resolved.
        assert host == "127.1"
        return [ipaddress.ip_address("127.0.0.1")]

    documents = ClientMetadataDocuments(
        _serving(httpx.Response(200, json=DOCUMENT), requests), resolver
    )

    # When
    client = asyncio.run(documents.get(url))

    # Then
    assert client is None
    assert requests == []


@pytest.mark.parametrize(
    ("host", "address"),
    [
        ("localhost", "127.0.0.1"),
        ("tiroir", "172.30.80.3"),
        ("metadata.internal", "169.254.169.254"),
        ("ipv6.internal", "::1"),
    ],
)
def test_name_resolving_to_a_private_address_is_refused(
    host: str, address: str
) -> None:
    # Given
    requests: list[httpx.Request] = []
    documents = ClientMetadataDocuments(
        _serving(httpx.Response(200, json=DOCUMENT), requests), _resolving(address)
    )

    # When
    client = asyncio.run(documents.get(f"https://{host}/client.json"))

    # Then
    assert client is None
    assert requests == []


def test_name_with_one_private_address_among_public_ones_is_refused() -> None:
    # Given
    requests: list[httpx.Request] = []

    async def resolver(host: str) -> list[IPAddress]:
        return [ipaddress.ip_address(PUBLIC), ipaddress.ip_address("10.0.0.1")]

    documents = ClientMetadataDocuments(
        _serving(httpx.Response(200, json=DOCUMENT), requests), resolver
    )

    # When
    client = asyncio.run(documents.get(URL))

    # Then
    assert client is None
    assert requests == []


def test_name_resolving_elsewhere_after_the_check_reaches_the_checked_address() -> None:
    # Given
    requests: list[httpx.Request] = []
    asked: list[str] = []
    documents = ClientMetadataDocuments(
        _serving(httpx.Response(200, json=DOCUMENT), requests),
        _resolving(PUBLIC, "127.0.0.1", asked=asked),
    )

    # When
    client = asyncio.run(documents.get(URL))

    # Then
    assert client is not None
    assert asked == ["client.example"]
    assert [request.url.host for request in requests] == [PUBLIC]


def test_unresolvable_name_is_refused() -> None:
    # Given
    requests: list[httpx.Request] = []

    async def resolver(host: str) -> list[IPAddress]:
        raise OSError("name or service not known")

    documents = ClientMetadataDocuments(
        _serving(httpx.Response(200, json=DOCUMENT), requests), resolver
    )

    # When
    client = asyncio.run(documents.get(URL))

    # Then
    assert client is None
    assert requests == []


def test_fetches_of_new_urls_are_limited_per_client_address(tmp_path: Path) -> None:
    # Given
    requests: list[httpx.Request] = []
    app = create_app(
        tmp_path,
        origin="https://testserver",
        http_transport=_serving(httpx.Response(404), requests),
        resolver=_resolving(PUBLIC),
    )

    def token_request(client: TestClient, index: int) -> None:
        client.post(
            "/oauth/token",
            data={
                "grant_type": "authorization_code",
                "client_id": f"https://client.example/c{index}",
                "code": "x",
                "redirect_uri": REDIRECT_URI,
                "code_verifier": "x" * 43,
            },
        )

    with (
        TestClient(
            app, base_url="https://testserver", client=("198.51.100.1", 1)
        ) as attacker,
        TestClient(
            app, base_url="https://testserver", client=("198.51.100.2", 1)
        ) as other,
    ):
        # When
        for index in range(DOCUMENT_FETCHES_PER_ADDRESS + 5):
            token_request(attacker, index)
        from_attacker = len(requests)
        token_request(other, 100)

    # Then
    assert from_attacker == DOCUMENT_FETCHES_PER_ADDRESS
    assert len(requests) == DOCUMENT_FETCHES_PER_ADDRESS + 1
