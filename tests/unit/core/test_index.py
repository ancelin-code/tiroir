"""The pure helpers of the index: metadata flattening, classifying, names."""

from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from tiroir.core.chunking import Kind
from tiroir.core.index import (
    _as_date,
    _author,
    _classify,
    _flatten,
    _frontmatter,
    _names,
)
from tiroir.core.schema import Schema, load_schema

SCHEMA = load_schema("""\
tiroir: 1
store:
  id: 0d6c1e9a-0000-4000-8000-000000000001
  name: firm
  audience: team
  language: fr
shared:
  path: notes
drawer_types:
  client:
    label: Client
    path: "clients/{code}"
    fields:
      code: {type: text, required: true}
      name: {type: text}
      aliases: {type: list}
    summary:
      template: templates/client.md
      sections: [Identity]
    detect:
      names: [code, name, aliases]
  project:
    label: Project
    path: "projects/{slug}"
    fields:
      slug: {type: text, required: true}
    summary:
      template: templates/project.md
      sections: [Goal]
""")


@pytest.fixture
def schema() -> Schema:
    """A schema with a client type (detect names) and a project type."""
    return SCHEMA


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Alice", ["Alice"]),
        (42, ["42"]),
        (True, ["true"]),
        (False, ["false"]),
        (None, []),
        ({"a": "b"}, []),
        (["a", None, True, 3], ["a", "true", "3"]),
        (date(2026, 3, 1), ["2026-03-01"]),
        (datetime(2026, 3, 1, 12, 30), ["2026-03-01"]),
        ([], []),
    ],
)
def test_flatten_gives_the_strings_a_value_filters_on(
    value: object, expected: list[str]
) -> None:
    # Given
    given = value

    # When
    result = _flatten(given)

    # Then
    assert result == expected


def test_as_date_converts_an_aware_datetime_to_utc() -> None:
    # Given
    value = datetime(2026, 3, 1, 23, 30, tzinfo=timezone(timedelta(hours=-2)))

    # When
    result = _as_date(value)

    # Then
    assert result == "2026-03-02"


def test_as_date_keeps_a_naive_datetime_and_a_date() -> None:
    # Given
    naive, plain = datetime(2026, 3, 1, 23, 30), date(2026, 3, 1)

    # When
    results = (_as_date(naive), _as_date(plain))

    # Then
    assert results == ("2026-03-01", "2026-03-01")


def test_as_date_ignores_other_values() -> None:
    # Given
    values = ["2026-03-01", None, 20260301]

    # When
    results = [_as_date(value) for value in values]

    # Then
    assert results == [None, None, None]
    assert _as_date(datetime(2026, 1, 1, tzinfo=UTC)) == "2026-01-01"


@pytest.mark.parametrize(
    ("fields", "expected"),
    [
        ({}, None),
        ({"author": None}, None),
        ({"author": ""}, None),
        ({"author": "  "}, None),
        ({"author": "Alice"}, "Alice"),
        ({"author": ["Alice", "Bob"]}, "Alice, Bob"),
    ],
)
def test_author_is_absent_rather_than_none_text(
    fields: dict[str, object], expected: str | None
) -> None:
    # Given
    given = fields

    # When
    author = _author(given)

    # Then
    assert author == expected


def test_frontmatter_splits_the_mapping_from_the_body() -> None:
    # Given
    text = "---\nauthor: Alice\n---\nBody\n"

    # When
    fields, body = _frontmatter(text)

    # Then
    assert fields == {"author": "Alice"}
    assert body.strip() == "Body"


def test_frontmatter_without_a_mapping_is_empty() -> None:
    # Given
    text = "---\n- a\n- b\n---\nBody\n"

    # When
    fields, _ = _frontmatter(text)

    # Then
    assert fields == {}


def test_classify_finds_summaries_logs_and_shared_notes(schema: Schema) -> None:
    # Given
    paths = [
        "clients/c001/summary.md",
        "clients/c001/log/2026-03-01-abcd.md",
        "notes/procedure.md",
    ]

    # When
    found = [_classify(schema, path) for path in paths]

    # Then
    assert [(c.kind, c.drawer, c.drawer_type) for c in found if c] == [
        (Kind.SUMMARY, "clients/c001", "client"),
        (Kind.LOG, "clients/c001", "client"),
        (Kind.SHARED, None, None),
    ]


@pytest.mark.parametrize(
    "path",
    [
        "tiroir.yaml",
        "templates/client.md",
        "notes/image.png",
        "clients/c001/notes.md",
        "clients/c001/log/entry.txt",
        "elsewhere/c001/summary.md",
    ],
)
def test_classify_ignores_other_files(schema: Schema, path: str) -> None:
    # Given
    given = path

    # When
    found = _classify(schema, given)

    # Then
    assert found is None


def test_names_use_the_detect_fields_folded_without_repeats(schema: Schema) -> None:
    # Given
    fields = {"code": "C001", "name": "Élan", "aliases": ["élan", "Bob"], "x": "y"}

    # When
    names = _names(schema, "client", fields)

    # Then
    assert names == ["c001", "elan", "bob"]


def test_names_skip_null_and_blank_values(schema: Schema) -> None:
    # Given
    fields = {"code": "C001", "name": None, "aliases": ["", " "]}

    # When
    names = _names(schema, "client", fields)

    # Then
    assert names == ["c001"]


def test_names_fall_back_to_the_path_fields(schema: Schema) -> None:
    # Given
    fields = {"slug": "Site-Web", "other": "x"}

    # When
    names = _names(schema, "project", fields)

    # Then
    assert names == ["site-web"]
