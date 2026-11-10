"""The memory skill's text, fingerprint and archive, from given schemas."""

import io
import zipfile
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from tiroir.core.schema import Schema, load_schema
from tiroir.core.skill import (
    DESCRIPTION_MAX_TOKENS,
    SKILL_PATH,
    GrantPrint,
    approx_tokens,
    description,
    fingerprint,
    schema_hash,
    skill_archive,
    skill_text,
)

FRENCH_SCHEMA = Path(__file__).parent / "schema" / "fixtures" / "valid-example.yaml"
TOOLS = (
    "tiroir_context",
    "tiroir_search",
    "tiroir_read",
    "tiroir_write",
    "tiroir_status",
)

ENGLISH = """\
tiroir: 1
store:
  id: 0b9a6f0e-2d4c-4f61-9a3e-5b7c8d9e0f12
  name: atelier-secret
  audience: personal
  language: en
shared:
  topics: [architecture, release process]
drawer_types:
  project:
    label: Project
    label_plural: Projects
    description: "A software project, by its repository."
    path: "projects/{slug}"
    fields:
      slug:
        type: text
        required: true
    summary:
      template: templates/project-summary.md
      sections: [Overview, Decisions]
"""


def _french() -> Schema:
    return load_schema(FRENCH_SCHEMA.read_text(encoding="utf-8"))


def _english() -> Schema:
    return load_schema(ENGLISH)


def _crowded() -> Schema:
    """An English schema with many long topics, to overflow the description."""
    topics = ", ".join(f"long shared topic number {n} about things" for n in range(40))
    return load_schema(
        ENGLISH.replace("[architecture, release process]", f"[{topics}]")
    )


def _frontmatter(text: str) -> dict[str, str]:
    """The YAML frontmatter of a `SKILL.md`, parsed."""
    head, _, _ = text.removeprefix("---\n").partition("\n---\n")
    return YAML(typ="safe").load(head)


def test_french_description_names_the_types_and_topics_within_the_cap() -> None:
    # Given
    schemas = [_french()]

    # When
    text = description(schemas)

    # Then
    assert "Clients" in text
    for topic in ("procédures", "modèles de lettres", "calendrier fiscal"):
        assert topic in text
    assert "À utiliser dès que" in text
    assert approx_tokens(text) <= DESCRIPTION_MAX_TOKENS


def test_english_description_is_in_english() -> None:
    # Given
    schemas = [_english()]

    # When
    text = description(schemas)

    # Then
    assert "Projects" in text
    assert "architecture" in text
    assert "Use it whenever" in text
    assert "À utiliser" not in text


def test_stores_of_both_languages_get_both_within_the_cap() -> None:
    # Given
    schemas = [_english(), _french()]

    # When
    text = description(schemas)

    # Then
    assert text.index("À utiliser") < text.index("Use it whenever")
    assert "Clients" in text
    assert "Projects" in text
    assert approx_tokens(text) <= DESCRIPTION_MAX_TOKENS


def test_too_many_topics_are_trimmed_to_the_cap() -> None:
    # Given
    schemas = [_crowded()]

    # When
    text = description(schemas)

    # Then
    assert approx_tokens(text) <= DESCRIPTION_MAX_TOKENS
    assert "Projects" in text
    assert "number 0 " in text
    assert "number 39 " not in text


def test_skill_never_names_the_store() -> None:
    # Given
    schemas = [_english(), _french()]

    # When
    text = skill_text(schemas)

    # Then
    assert "atelier-secret" not in text
    assert "cabinet-exemple" not in text


@pytest.mark.parametrize(
    ("schema", "phrases"),
    [
        (
            _french(),
            (
                "mémoire d'équipe",
                "accord explicite",
                "entrée de journal pour chaque fait nouveau, décision, échéance",
                "proposition de mise à jour de la synthèse",
                "rien quand la conversation n'établit rien de nouveau",
            ),
        ),
        (
            _english(),
            (
                "team memory",
                "explicit agreement",
                "log entry for each new fact, decision, deadline or document",
                "summary update proposal when a durable fact changes",
                "nothing when the conversation establishes nothing new",
            ),
        ),
    ],
)
def test_body_names_the_tools_the_confirmation_rule_and_when_to_write(
    schema: Schema, phrases: tuple[str, ...]
) -> None:
    # Given
    schemas = [schema]

    # When
    text = skill_text(schemas)

    # Then
    body = text.partition("\n---\n")[2]
    for tool in TOOLS:
        assert f"`{tool}`" in body
    for phrase in phrases:
        assert phrase in body.replace("\n  ", " ").replace("\n", " ")


def test_a_member_with_no_store_still_gets_a_valid_skill() -> None:
    # Given
    schemas: list[Schema] = []

    # When
    text = skill_text(schemas)

    # Then
    assert "Use it whenever" in _frontmatter(text)["description"]
    assert "`tiroir_context`" in text
    assert "## What the memory holds" not in text


def test_frontmatter_holds_the_name_and_the_description() -> None:
    # Given
    schemas = [_french()]

    # When
    text = skill_text(schemas)

    # Then
    assert _frontmatter(text) == {
        "name": "tiroir-memory",
        "description": description(schemas),
    }


def test_archive_unzips_to_the_skill_file() -> None:
    # Given
    text = skill_text([_french()])

    # When
    data = skill_archive(text)

    # Then
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert archive.namelist() == [SKILL_PATH]
        assert archive.read(SKILL_PATH).decode("utf-8") == text


def test_archive_is_the_same_for_the_same_text() -> None:
    # Given
    text = skill_text([_english()])

    # When
    first, second = skill_archive(text), skill_archive(text)

    # Then
    assert first == second


def test_fingerprint_ignores_the_order_of_the_grants() -> None:
    # Given
    a = GrantPrint("s1", "write", schema_hash(b"one"))
    b = GrantPrint("s2", "read", schema_hash(b"two"))

    # When
    forward, backward = fingerprint([a, b]), fingerprint([b, a])

    # Then
    assert forward == backward


@pytest.mark.parametrize(
    "changed",
    [
        [GrantPrint("s1", "write", schema_hash(b"one, edited"))],
        [GrantPrint("s1", "read", schema_hash(b"one"))],
        [
            GrantPrint("s1", "write", schema_hash(b"one")),
            GrantPrint("s2", "read", schema_hash(b"two")),
        ],
        [],
    ],
)
def test_fingerprint_changes_with_a_grant_or_a_schema(
    changed: list[GrantPrint],
) -> None:
    # Given
    before = [GrantPrint("s1", "write", schema_hash(b"one"))]

    # When
    original, other = fingerprint(before), fingerprint(changed)

    # Then
    assert original != other


def test_approx_tokens_counts_one_token_per_three_and_a_half_characters() -> None:
    # Given
    text = "x" * 8

    # When
    count = approx_tokens(text)

    # Then
    assert count == 3
