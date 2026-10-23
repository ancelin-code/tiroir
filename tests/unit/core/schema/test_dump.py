"""Tests for writing the schema in canonical form."""

from pathlib import Path

from tiroir.core.schema import dump_schema, load_schema

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_contract_example_round_trips_to_canonical_text() -> None:
    # Given
    text = fixture("valid-example.yaml")

    # When
    dumped = dump_schema(load_schema(text))

    # Then
    assert dumped == text
    assert dump_schema(load_schema(dumped)) == dumped
