import pytest

from tiroir.cli.admin import proxy_options, trusted_proxies


def test_trusted_proxies_are_ip_networks() -> None:
    # Given
    value = "172.30.80.0/24, 127.0.0.1,::1"

    # When
    proxies = trusted_proxies(value)

    # Then
    assert proxies == ["172.30.80.0/24", "127.0.0.1/32", "::1/128"]


@pytest.mark.parametrize("value", ["*", "", " , ", "caddy", "172.30.80.0/24,*"])
def test_wildcard_or_name_is_no_trusted_proxy(value: str) -> None:
    # Given
    candidate = value

    # When
    with pytest.raises(ValueError) as raised:
        trusted_proxies(candidate)

    # Then
    assert raised.value is not None


def test_proxy_options_read_forwarded_headers_from_those_proxies_only() -> None:
    # Given
    proxies = ["172.30.80.0/24"]

    # When
    options = proxy_options(proxies)

    # Then
    assert options == {"proxy_headers": True, "forwarded_allow_ips": proxies}
