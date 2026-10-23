import asyncio
import json
from pathlib import Path

import httpx
import pytest
from mcp.shared.auth import OAuthClientInformationFull
from starlette.testclient import TestClient

from tiroir.server.app import create_app
from tiroir.server.auth.oauth import DOCUMENT_MAX_BYTES, ClientMetadataDocuments

URL = "https://client.example/oauth/client.json"
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


def test_document_is_fetched_once_then_cached() -> None:
    # Given
    requests: list[httpx.Request] = []
    documents = ClientMetadataDocuments(
        _serving(httpx.Response(200, json=DOCUMENT), requests)
    )

    async def twice() -> list[OAuthClientInformationFull | None]:
        return [await documents.get(URL), await documents.get(URL)]

    # When
    clients = asyncio.run(twice())

    # Then
    assert len(requests) == 1
    assert requests[0].url == URL
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
    ],
)
def test_url_that_cannot_name_a_client_is_not_fetched(url: str) -> None:
    # Given
    requests: list[httpx.Request] = []
    documents = ClientMetadataDocuments(
        _serving(httpx.Response(200, json=DOCUMENT), requests)
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
    documents = ClientMetadataDocuments(_serving(answer))

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

    documents = ClientMetadataDocuments(httpx.MockTransport(slow))

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
