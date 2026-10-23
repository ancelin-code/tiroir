import ipaddress
import json

import pytest

from tiroir.server.auth.oauth import (
    address_public,
    client_from_document,
    metadata_document_url_valid,
    redirect_uri_allowed,
)

URL = "https://client.example/oauth/client.json"


@pytest.mark.parametrize(
    ("url", "valid"),
    [
        (URL, True),
        ("https://client.example:443/c", True),
        ("https://client.example:8443/c", False),
        ("https://client.example:80/c", False),
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


@pytest.mark.parametrize(
    ("address", "public"),
    [
        ("93.184.215.14", True),
        ("2606:2800:21f:cb07:6820:80da:af6b:8b2c", True),
        ("127.0.0.1", False),
        ("10.1.2.3", False),
        ("172.16.0.1", False),
        ("192.168.0.1", False),
        ("169.254.169.254", False),
        ("100.64.0.1", False),
        ("224.0.0.1", False),
        ("233.252.0.1", False),
        ("0.0.0.0", False),
        ("255.255.255.255", False),
        ("::1", False),
        ("::", False),
        ("fe80::1", False),
        ("fc00::1", False),
        ("ff0e::1", False),
        ("::ffff:127.0.0.1", False),
        ("::ffff:93.184.215.14", False),
        ("64:ff9b::7f00:1", False),
        ("2002:7f00:1::1", False),
        ("2001:0:4136:e378:8000:63bf:3fff:fdd2", False),
    ],
)
def test_only_global_unicast_addresses_are_public(address: str, public: bool) -> None:
    # Given
    candidate = ipaddress.ip_address(address)

    # When
    result = address_public(candidate)

    # Then
    assert result is public


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


@pytest.mark.parametrize(
    ("uri", "allowed"),
    [
        ("https://app.example/callback", True),
        ("https://app.example:8443/cb?x=1", True),
        ("http://127.0.0.1:33418/callback", True),
        ("http://127.0.0.1/callback", True),
        ("http://[::1]:8080/cb", True),
        ("http://localhost:3000/cb", True),
        ("com.example.app:/callback", True),
        ("com.example.app://callback", True),
        ("http://app.example/cb", False),
        ("http://127.0.0.2/cb", False),
        ("http://localhost.attacker.example/cb", False),
        ("https://app.example/cb#f", False),
        ("https://app.example/cb#", False),
        ("https:///cb", False),
        ("https://app.example:99999/cb", False),
        ("cursor://anysphere.cursor-mcp/oauth/callback", False),
        ("javascript:alert(1)", False),
        ("JavaScript:alert(1)", False),
        ("data:text/html,x", False),
        ("file:///etc/passwd", False),
        ("vbscript:x", False),
        ("blob:https://app.example/x", False),
        ("com.example.app", False),
        ("", False),
    ],
)
def test_redirect_uri_rules(uri: str, allowed: bool) -> None:
    # Given
    candidate = uri

    # When
    verdict = redirect_uri_allowed(candidate)

    # Then
    assert verdict is allowed
