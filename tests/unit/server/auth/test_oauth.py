import json

import pytest

from tiroir.server.auth.oauth import client_from_document, metadata_document_url_valid

URL = "https://client.example/oauth/client.json"


@pytest.mark.parametrize(
    ("url", "valid"),
    [
        (URL, True),
        ("https://client.example:8443/c", True),
        ("http://client.example/c", False),
        ("https://client.example", False),
        ("https://client.example/", False),
        ("https://u@client.example/c", False),
        ("https://client.example/./c", False),
        ("https://client.example/c#f", False),
        ("https://client.example:99999/c", False),
        ("https:///c", False),
    ],
)
def test_metadata_document_url_rules(url: str, valid: bool) -> None:
    # Given
    candidate = url

    # When
    result = metadata_document_url_valid(candidate)

    # Then
    assert result is valid


def test_document_describes_a_public_client() -> None:
    # Given
    body = json.dumps(
        {"client_id": URL, "client_name": "C", "redirect_uris": ["http://127.0.0.1/cb"]}
    ).encode()

    # When
    client = client_from_document(URL, body)

    # Then
    assert client is not None
    assert client.client_id == URL
    assert client.client_secret is None
    assert [str(u) for u in client.redirect_uris or []] == ["http://127.0.0.1/cb"]


@pytest.mark.parametrize(
    "document",
    [
        [],
        {"client_id": "https://other.example/c", "redirect_uris": ["http://a/cb"]},
        {"client_id": URL},
        {"client_id": URL, "redirect_uris": ["http://a/cb"], "client_secret": "s"},
        {
            "client_id": URL,
            "redirect_uris": ["http://a/cb"],
            "token_endpoint_auth_method": "private_key_jwt",
        },
        {"client_id": URL, "redirect_uris": "not a list"},
    ],
)
def test_document_that_is_no_public_client_is_refused(document: object) -> None:
    # Given
    body = json.dumps(document).encode()

    # When
    client = client_from_document(URL, body)

    # Then
    assert client is None
