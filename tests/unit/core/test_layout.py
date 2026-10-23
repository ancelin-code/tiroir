"""Tests for the store layout: slugs, paths, frontmatter, MEMORY.md, messages."""

import re
from datetime import UTC, date, datetime, timedelta, timezone

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tiroir.core.errors import CoreError
from tiroir.core.layout import (
    Drawer,
    commit_message,
    drawer_path,
    drawer_pattern,
    drawers_in,
    log_entry_path,
    new_suffix,
    render_frontmatter,
    render_log_entry,
    render_memory,
    render_summary,
    slug,
    split_frontmatter,
)
from tiroir.core.schema import load_schema
from tiroir.core.yaml_io import load_yaml

SCHEMA = """\
tiroir: 1
store:
  id: 0d6c1e9a-0000-4000-8000-000000000001
  name: cabinet-exemple
  audience: personal
  language: fr
  description: "Mémoire du cabinet."
drawer_types:
  client:
    label: Client
    label_plural: Clients
    path: "clients/{code}"
    fields:
      code: {type: text, required: true}
      name: {type: text, required: true}
      aliases: {type: list}
      fiscal_year_end: {type: date}
    summary:
      template: templates/client-summary.md
      sections: [Identité]
    detect:
      names: [code, name, aliases]
  project:
    label: Project
    path: "projects/{name}"
    fields:
      name: {type: text, required: true}
    summary:
      template: templates/project-summary.md
      sections: [Goal]
"""


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Boulangerie Dupont & Fils", "boulangerie-dupont-fils"),
        ("C042", "c042"),
        ("  Élan -- Été  ", "elan-ete"),
        ("ﬁche Nº 5", "fiche-no-5"),
        ("!!!", ""),
    ],
)
def test_slug_follows_the_contract(text: str, expected: str) -> None:
    # Given
    # a name as a member would write it

    # When
    result = slug(text)

    # Then
    assert result == expected


@given(st.text())
def test_slug_is_short_lowercase_and_trimmed(text: str) -> None:
    # Given
    # any text

    # When
    result = slug(text)

    # Then
    assert len(result) <= 64
    assert re.fullmatch(r"([a-z0-9]+(-[a-z0-9]+)*)?", result)


def test_drawer_path_slugs_each_placeholder() -> None:
    # Given
    client = load_schema(SCHEMA).drawer_types["client"]

    # When
    path = drawer_path(client, {"code": "C042", "name": "Boulangerie Dupont"})

    # Then
    assert path == "clients/c042"


def test_drawer_path_without_its_placeholder_value_is_refused() -> None:
    # Given
    client = load_schema(SCHEMA).drawer_types["client"]

    # When
    with pytest.raises(CoreError) as caught:
        drawer_path(client, {"code": "---", "name": "Dupont"})

    # Then
    assert caught.value.code == "metadata.invalid"


@pytest.mark.parametrize(
    ("folder", "matches"),
    [
        ("clients/c042", True),
        ("clients/boulangerie-dupont", True),
        ("clients/C042", False),
        ("clients/c042/log", False),
        ("clientsx/c042", False),
    ],
)
def test_drawer_pattern_matches_the_folders_it_produces(
    folder: str, matches: bool
) -> None:
    # Given
    client = load_schema(SCHEMA).drawer_types["client"]

    # When
    found = drawer_pattern(client).fullmatch(folder) is not None

    # Then
    assert found is matches


def test_log_entry_path_is_dated_in_utc() -> None:
    # Given
    paris = timezone(timedelta(hours=2))
    when = datetime(2026, 10, 21, 16, 32, 5, tzinfo=paris)

    # When
    path = log_entry_path("clients/c042", when, "alice", "k3f9")

    # Then
    assert path == "clients/c042/log/2026/10/2026-10-21T143205Z-alice-k3f9.md"


def test_new_suffix_is_four_lowercase_alphanumerics() -> None:
    # Given
    count = 50

    # When
    suffixes = [new_suffix() for _ in range(count)]

    # Then
    assert all(re.fullmatch(r"[a-z0-9]{4}", s) for s in suffixes)


def test_log_entry_has_date_and_author_frontmatter() -> None:
    # Given
    when = datetime(2026, 10, 21, 14, 32, 5, tzinfo=UTC)

    # When
    text = render_log_entry(when, "alice", "Relance envoyée.")

    # Then
    assert text == (
        "---\ndate: 2026-10-21T14:32:05Z\nauthor: alice\n---\nRelance envoyée.\n"
    )


def test_frontmatter_is_canonical() -> None:
    # Given
    data = {
        "type": "client",
        "name": "Dupont: père & fils",
        "aliases": ["Dupont", "BD"],
        "fiscal_year_end": date(2025, 12, 31),
    }

    # When
    text = render_frontmatter(data)

    # Then
    assert text == (
        "---\n"
        "type: client\n"
        'name: "Dupont: père & fils"\n'
        "aliases: [Dupont, BD]\n"
        "fiscal_year_end: 2025-12-31\n"
        "---\n"
    )


def test_split_frontmatter_returns_yaml_and_body() -> None:
    # Given
    text = "---\ntype: client\n---\n# Title\n"

    # When
    yaml_text, body = split_frontmatter(text)

    # Then
    assert yaml_text == "type: client\n"
    assert body == "# Title\n"


def test_split_frontmatter_without_one_keeps_the_text() -> None:
    # Given
    text = "# Title\n"

    # When
    yaml_text, body = split_frontmatter(text)

    # Then
    assert yaml_text is None
    assert body == text


def test_summary_has_type_then_fields_in_schema_order() -> None:
    # Given
    schema = load_schema(SCHEMA)
    fields = {"name": "Boulangerie Dupont", "code": "C042"}
    template = "# {name}\n\n## Identité\n\n{unknown} stays.\n"

    # When
    text = render_summary("client", schema.drawer_types["client"], fields, template)

    # Then
    assert text == (
        "---\ntype: client\ncode: C042\nname: Boulangerie Dupont\n---\n"
        "# Boulangerie Dupont\n\n## Identité\n\n{unknown} stays.\n"
    )


def test_drawers_are_found_from_their_summaries() -> None:
    # Given
    schema = load_schema(SCHEMA)
    summaries = {
        "clients/c002/summary.md": "---\ntype: client\ncode: C002\nname: B\n---\n",
        "clients/c001/summary.md": "---\ntype: client\ncode: C001\nname: A\n---\n",
        "shared/summary.md": "not a drawer\n",
    }

    # When
    drawers = drawers_in(schema, summaries)

    # Then
    assert [(d.id, d.type, d.fields["code"]) for d in drawers] == [
        ("clients/c001", "client", "C001"),
        ("clients/c002", "client", "C002"),
    ]


def test_drawer_with_unreadable_frontmatter_is_refused() -> None:
    # Given
    schema = load_schema(SCHEMA)
    summaries = {"clients/c001/summary.md": "---\ncode: [\n---\n"}

    # When
    with pytest.raises(CoreError) as caught:
        drawers_in(schema, summaries)

    # Then
    assert caught.value.code == "metadata.invalid"


def test_memory_lists_drawers_by_type_sorted_by_id() -> None:
    # Given
    schema = load_schema(SCHEMA)
    drawers = [
        Drawer("projects/site", "project", {"name": "Site"}),
        Drawer(
            "clients/c002",
            "client",
            load_yaml("code: C002\nname: Durand\naliases: [D]\n"),
        ),
        Drawer("clients/c001", "client", {"code": "C001", "name": "Dupont"}),
    ]

    # When
    text = render_memory(schema, drawers)

    # Then
    assert text == (
        "# cabinet-exemple\n\n"
        "Mémoire du cabinet.\n\n"
        "Chaque tiroir est un dossier qui contient `summary.md`, sa fiche, et "
        "`log/`, son journal daté. Les documents partagés sont dans `shared/`.\n\n"
        "## Clients\n\n"
        "- [[clients/c001/summary]] — Client: C001, Dupont\n"
        "- [[clients/c002/summary]] — Client: C002, Durand, D\n\n"
        "## Project\n\n"
        "- [[projects/site/summary]] — Project: Site\n"
    )


def test_commit_message_carries_subject_and_trailers() -> None:
    # Given
    op, author, via, drawer = "log-append", "alice", "mcp", "clients/c042"

    # When
    message = commit_message(op, author, via, drawer)

    # Then
    assert message == (
        "tiroir: log-append clients/c042\n\n"
        "Tiroir-Op: log-append\n"
        "Tiroir-Drawer: clients/c042\n"
        "Tiroir-Author: alice\n"
        "Tiroir-Via: mcp\n"
    )


def test_store_commit_message_names_the_store() -> None:
    # Given
    op, author, via = "store-init", "alice", "cli"

    # When
    message = commit_message(op, author, via)

    # Then
    assert message == (
        "tiroir: store-init store\n\n"
        "Tiroir-Op: store-init\nTiroir-Author: alice\nTiroir-Via: cli\n"
    )
