"""Tests for loading, validating and writing the store schema."""

from pathlib import Path
from typing import Any

import pytest

from tiroir.core.errors import CoreError
from tiroir.core.schema import (
    DrawerType,
    dump_schema,
    load_schema,
    validate_metadata,
)
from tiroir.core.yaml_io import load_yaml

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def client_type() -> DrawerType:
    return load_schema(fixture("valid-example.yaml")).drawer_types["client"]


def test_contract_example_loads() -> None:
    # Given
    text = fixture("valid-example.yaml")

    # When
    schema = load_schema(text)

    # Then
    client = schema.drawer_types["client"]
    assert schema.store.name == "cabinet-exemple"
    assert schema.store.audience == "team"
    assert client.path == "clients/{code}"
    assert list(client.fields) == [
        "code",
        "name",
        "aliases",
        "legal_form",
        "fiscal_year_end",
    ]
    assert client.fields["code"].is_required
    assert client.summary.sections[3] == "Contacts"
    assert client.detect is not None
    assert client.detect.names == ("code", "name", "aliases")
    assert schema.shared_path == "shared"
    assert schema.conventions_max_tokens == 1500
    assert client.inject_max_tokens == 800


def test_contract_example_round_trips_to_canonical_text() -> None:
    # Given
    text = fixture("valid-example.yaml")

    # When
    dumped = dump_schema(load_schema(text))

    # Then
    assert dumped == text
    assert dump_schema(load_schema(dumped)) == dumped


def test_defaults_apply_when_keys_are_absent() -> None:
    # Given
    schema = load_schema(fixture("valid-example.yaml"))
    client = schema.drawer_types["client"]

    # When
    sections = client.inject_sections

    # Then
    assert sections == ("Identité", "Points d'attention", "Échéances")
    assert schema.shared is not None
    assert schema.shared.path is None


@pytest.mark.parametrize(
    ("name", "code", "path"),
    [
        ("invalid-unknown-key.yaml", "schema.invalid", "drawer_types.client.colour"),
        (
            "invalid-wrong-type.yaml",
            "schema.invalid",
            "drawer_types.client.fields.fiscal_year_end.type",
        ),
        ("invalid-missing-required.yaml", "schema.invalid", "store.language"),
        ("invalid-syntax.yaml", "schema.invalid", ""),
        ("invalid-anchor.yaml", "schema.invalid", ""),
        ("invalid-tag.yaml", "schema.invalid", ""),
        ("invalid-two-documents.yaml", "schema.invalid", ""),
        ("unsupported-version.yaml", "schema.unsupported-version", "tiroir"),
        (
            "invalid-path-no-placeholder.yaml",
            "schema.invalid-path",
            "drawer_types.client.path",
        ),
        (
            "invalid-path-optional-placeholder.yaml",
            "schema.invalid-path",
            "drawer_types.client.path",
        ),
        (
            "invalid-path-escape.yaml",
            "schema.invalid-path",
            "drawer_types.client.path",
        ),
        (
            "invalid-overlap.yaml",
            "schema.invalid-path",
            "drawer_types.client.path",
        ),
        (
            "unknown-section.yaml",
            "schema.unknown-section",
            "drawer_types.client.inject.sections[1]",
        ),
        (
            "invalid-detect.yaml",
            "schema.invalid-detect",
            "drawer_types.client.detect.names[1]",
        ),
    ],
)
def test_each_error_case_yields_its_code(name: str, code: str, path: str) -> None:
    # Given
    text = fixture(name)

    # When
    with pytest.raises(CoreError) as raised:
        load_schema(text)

    # Then
    error = raised.value
    assert error.code == code
    assert [(v.code, v.path) for v in error.violations][0] == (code, path)


def test_violation_line_points_at_the_key() -> None:
    # Given
    text = fixture("invalid-wrong-type.yaml")
    expected = text.splitlines().index("        type: datetime") + 1

    # When
    with pytest.raises(CoreError) as raised:
        load_schema(text)

    # Then
    assert [v.line for v in raised.value.violations] == [expected]


def test_three_independent_errors_are_all_reported() -> None:
    # Given
    text = fixture("invalid-three-errors.yaml")
    lines = text.splitlines()

    # When
    with pytest.raises(CoreError) as raised:
        load_schema(text)

    # Then
    found = [(v.path, v.line) for v in raised.value.violations]
    assert found == [
        ("store.audience", lines.index("store:") + 1),
        ("drawer_types.client.colour", lines.index("    colour: blue") + 1),
        (
            "drawer_types.client.fields.fiscal_year_end.type",
            lines.index("        type: datetime") + 1,
        ),
    ]
    assert "3 violations" in str(raised.value)


def test_violations_do_not_echo_values() -> None:
    # Given
    text = fixture("invalid-wrong-type.yaml")

    # When
    with pytest.raises(CoreError) as raised:
        load_schema(text)

    # Then
    assert "datetime" not in raised.value.message


def test_yaml_11_words_stay_strings_in_the_schema() -> None:
    # Given
    original = "values: [EI, SARL, SAS, SCI, Association]\n"
    replacement = "values: [no, on, yes]\n        default: no\n"
    text = fixture("valid-example.yaml").replace(original, replacement)

    # When
    schema = load_schema(text)

    # Then
    legal_form = schema.drawer_types["client"].fields["legal_form"]
    assert legal_form.values == ("no", "on", "yes")
    assert legal_form.default == "no"
    assert '"no"' in dump_schema(schema)


def test_empty_text_is_invalid() -> None:
    # Given
    text = ""

    # When
    with pytest.raises(CoreError) as raised:
        load_schema(text)

    # Then
    assert raised.value.code == "schema.invalid"


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
