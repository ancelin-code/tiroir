"""Static checks of the deployment files: `compose.yaml` and the Caddyfile."""

from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

ROOT = Path(__file__).resolve().parents[2]


def _compose() -> dict[str, Any]:
    return YAML(typ="safe").load(ROOT / "compose.yaml")


def test_only_caddy_publishes_ports() -> None:
    # Given
    services = _compose()["services"]

    # When
    published = {name: service.get("ports") for name, service in services.items()}

    # Then
    assert set(services) == {"tiroir", "caddy"}
    assert published["tiroir"] is None
    assert published["caddy"] == ["80:80", "443:443"]


def test_tiroir_keeps_its_state_in_the_named_volume() -> None:
    # Given
    compose = _compose()

    # When
    mounts = compose["services"]["tiroir"]["volumes"]

    # Then
    assert mounts == ["tiroir-data:/data"]
    assert "tiroir-data" in compose["volumes"]


def test_caddy_keeps_its_certificates_and_config_in_volumes() -> None:
    # Given
    compose = _compose()

    # When
    mounts = compose["services"]["caddy"]["volumes"]

    # Then
    assert "caddy-data:/data" in mounts
    assert "caddy-config:/config" in mounts
    assert {"caddy-data", "caddy-config"} <= set(compose["volumes"])


def test_image_tag_and_domain_come_from_the_environment_file() -> None:
    # Given
    services = _compose()["services"]

    # When
    image = services["tiroir"]["image"]
    domain = services["caddy"]["environment"]["TIROIR_DOMAIN"]

    # Then
    assert "${TIROIR_TAG" in image
    assert domain.startswith("${TIROIR_DOMAIN")


def test_caddy_requires_the_domain_and_the_acme_email() -> None:
    # Given
    environment = _compose()["services"]["caddy"]["environment"]

    # When
    required = {name: ":?" in value for name, value in environment.items()}

    # Then
    # Caddy fails to parse an empty `email`, so neither may fall back to "".
    assert required == {"TIROIR_DOMAIN": True, "TIROIR_ACME_EMAIL": True}


def test_caddyfile_proxies_the_domain_to_tiroir_without_buffering() -> None:
    # Given
    caddyfile = (ROOT / "deploy" / "Caddyfile").read_text()

    # When
    lines = [line.strip() for line in caddyfile.splitlines()]

    # Then
    assert "{$TIROIR_DOMAIN} {" in lines
    assert "reverse_proxy tiroir:8080 {" in lines
    assert "flush_interval -1" in lines
    assert any(line.startswith("email {$TIROIR_ACME_EMAIL") for line in lines)


def test_env_example_sets_every_variable_the_stack_reads() -> None:
    # Given
    names = {
        line.split("=", 1)[0]
        for line in (ROOT / ".env.example").read_text().splitlines()
        if "=" in line and not line.startswith("#")
    }

    # When
    expected = {
        "TIROIR_DOMAIN",
        "TIROIR_ACME_EMAIL",
        "TIROIR_TAG",
        "TIROIR_PROXY_SUBNET",
    }

    # Then
    assert names == expected


def test_tiroir_trusts_forwarded_addresses_from_the_stack_network_only() -> None:
    # Given
    compose = _compose()

    # When
    trusted = compose["services"]["tiroir"]["environment"]["TIROIR_TRUSTED_PROXIES"]
    subnets = [
        entry["subnet"] for entry in compose["networks"]["default"]["ipam"]["config"]
    ]

    # Then
    assert subnets == [trusted]
    assert trusted.startswith("${TIROIR_PROXY_SUBNET:-")
    assert "*" not in trusted


def test_tiroir_knows_its_public_domain() -> None:
    # Given
    compose = _compose()

    # When
    environment = compose["services"]["tiroir"]["environment"]

    # Then
    assert (
        environment["TIROIR_DOMAIN"]
        == compose["services"]["caddy"]["environment"]["TIROIR_DOMAIN"]
    )
