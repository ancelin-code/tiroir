"""Tests for the shared YAML 1.2 reader and canonical writer."""

from datetime import date
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tiroir.core.yaml_io import YamlError, dump_yaml, key_line, load_yaml


@pytest.mark.parametrize("word", ["no", "on", "yes", "off", "y", "n"])
def test_yaml_11_booleans_stay_strings(word: str) -> None:
    # Given
    text = f"answer: {word}\n"

    # When
    data = load_yaml(text)

    # Then
    assert data["answer"] == word
    assert isinstance(data["answer"], str)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("a: &x 1\n", "anchors"),
        ("a: &x 1\nb: *x\n", "anchors"),
        ("a: !!str 1\n", "tags"),
        ("a: 1\n---\nb: 2\n", "multiple documents"),
        ("a: 1\na: 2\n", "duplicate"),
        ("%YAML 1.1\n---\na: yes\n", "directives"),
        ("%TAG !e! tag:example.com,2000:\n---\na: 1\n", "directives"),
    ],
)
def test_unsupported_constructs_are_refused(text: str, message: str) -> None:
    # Given
    # a document using a construct ADR-003 forbids

    # When
    with pytest.raises(YamlError) as raised:
        load_yaml(text)

    # Then
    assert message in raised.value.message
    assert raised.value.line is not None


def test_syntax_error_reports_its_line() -> None:
    # Given
    text = "a: 1\nb: [2\n"

    # When
    with pytest.raises(YamlError) as raised:
        load_yaml(text)

    # Then
    assert raised.value.line is not None
    assert raised.value.line >= 2


def test_unreadable_character_is_a_yaml_error() -> None:
    # Given
    text = "a: \x07\n"

    # When
    with pytest.raises(YamlError) as raised:
        load_yaml(text)

    # Then
    assert raised.value.message == "invalid YAML"


def test_key_line_is_one_based() -> None:
    # Given
    data = load_yaml("a: 1\nb:\n  c: 2\n")

    # When
    lines = (key_line(data, "a"), key_line(data, "b"), key_line(data["b"], "c"))

    # Then
    assert lines == (1, 2, 3)


def test_dump_is_canonical() -> None:
    # Given
    data: dict[str, Any] = {
        "name": "acme",
        "when": date(2026, 1, 31),
        "count": 3,
        "ratio": 1.5,
        "flag": True,
        "tags": ["a", "b c"],
        "empty": [],
        "text": "needs: quoting",
        "digits": "0042",
        "answer": "no",
        "nested": {"inner": "é"},
    }

    # When
    text = dump_yaml(data)

    # Then
    assert text == (
        "name: acme\n"
        "when: 2026-01-31\n"
        "count: 3\n"
        "ratio: 1.5\n"
        "flag: true\n"
        "tags: [a, b c]\n"
        "empty: []\n"
        'text: "needs: quoting"\n'
        'digits: "0042"\n'
        'answer: "no"\n'
        "nested:\n"
        "  inner: é\n"
    )


def test_dump_separates_top_level_entries_on_request() -> None:
    # Given
    data = {"a": 1, "b": {"c": 2, "d": 3}, "e": 4}

    # When
    text = dump_yaml(data, separate_top_level=True)

    # Then
    assert text == "a: 1\n\nb:\n  c: 2\n  d: 3\n\ne: 4\n"


def test_dump_refuses_a_list_of_mappings() -> None:
    # Given
    data = {"a": [{"b": 1}]}

    # When
    with pytest.raises(TypeError) as raised:
        dump_yaml(data)

    # Then
    assert "scalar" in str(raised.value)


_scalars = st.one_of(
    st.text(),
    st.integers(),
    st.booleans(),
    st.dates(),
    st.floats(allow_nan=False, allow_infinity=False),
)
_keys = st.from_regex(r"[a-z][a-z0-9_]{0,8}", fullmatch=True)


@given(
    st.dictionaries(
        _keys,
        st.one_of(_scalars, st.lists(st.text(), max_size=4)),
        max_size=5,
    )
)
def test_dump_then_load_round_trips(data: dict[str, Any]) -> None:
    # Given
    text = dump_yaml(data)

    # When
    loaded = load_yaml(text)

    # Then
    assert (loaded or {}) == data
    assert dump_yaml(loaded or {}) == text
