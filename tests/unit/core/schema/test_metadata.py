"""Tests for checking a summary's frontmatter against its drawer type."""

from pathlib import Path
from typing import Any

from tiroir.core.schema import DrawerType, load_schema, validate_metadata
from tiroir.core.yaml_io import load_yaml

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def client_type() -> DrawerType:
    return load_schema(fixture("valid-example.yaml")).drawer_types["client"]


def valid_client() -> dict[str, Any]:
    return load_yaml(
        "type: client\n"
        "code: C042\n"
        "name: Dupont SARL\n"
        "aliases: [Dupont, Dupont et fils]\n"
        "legal_form: SARL\n"
        "fiscal_year_end: 2026-12-31\n"
    )


def test_valid_client_metadata_is_accepted() -> None:
    # Given
    drawer_type = client_type()
    metadata = valid_client()

    # When
    violations = validate_metadata(drawer_type, metadata)

    # Then
    assert violations == []


def test_invalid_client_metadata_reports_every_violation() -> None:
    # Given
    drawer_type = client_type()
    metadata = load_yaml(
        "code: X1\n"
        "aliases: Dupont\n"
        "legal_form: GIE\n"
        "fiscal_year_end: 31/12/2026\n"
        "colour: blue\n"
    )

    # When
    violations = validate_metadata(drawer_type, metadata)

    # Then
    assert {v.path for v in violations} == {
        "code",
        "name",
        "aliases",
        "legal_form",
        "fiscal_year_end",
        "colour",
    }
    assert {v.code for v in violations} == {"metadata.invalid"}
    assert next(v for v in violations if v.path == "code").line == 1
    assert "X1" not in " ".join(str(v) for v in violations)


def test_empty_metadata_misses_only_required_fields() -> None:
    # Given
    drawer_type = client_type()

    # When
    violations = validate_metadata(drawer_type, {})

    # Then
    assert [v.path for v in violations] == ["code", "name"]
