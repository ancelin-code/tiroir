"""Shared YAML 1.2 reader and canonical writer (ADR-003).

Reading refuses anchors, aliases, tags and multiple documents. Writing is
done here, not by the YAML library, so the output is the same across library
versions: block mappings, scalar lists in flow style, strings plain when that
is safe and double-quoted otherwise.
"""

import json
import math
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from functools import lru_cache
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.error import MarkedYAMLError, YAMLError
from ruamel.yaml.events import (
    AliasEvent,
    CollectionStartEvent,
    DocumentStartEvent,
    NodeEvent,
    ScalarEvent,
)

# Words YAML 1.1 readers (Obsidian among them) turn into booleans.
_YAML_11_BOOLEANS = frozenset({"y", "n", "yes", "no", "on", "off"})
_PLAIN_CHARS = frozenset(" _./-'")


class YamlError(ValueError):
    """The text is not acceptable YAML; `line` is 1-based when known."""

    def __init__(self, message: str, line: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.line = line


def _reader() -> YAML:
    """A round-trip YAML 1.2 reader that refuses duplicate keys."""
    yaml = YAML(typ="rt")
    yaml.version = (1, 2)
    yaml.allow_duplicate_keys = False
    return yaml


def _line(mark: Any) -> int | None:
    """The 1-based line of a parser mark, or `None`."""
    return None if mark is None else int(mark.line) + 1


def _refuse_unsupported(text: str) -> None:
    """Raise `YamlError` unless `text` is one YAML document with no 1.1 directive."""
    documents = 0
    for event in _reader().parse(text):
        if isinstance(event, DocumentStartEvent):
            documents += 1
            if documents > 1:
                raise YamlError(
                    "multiple documents are not allowed", _line(event.start_mark)
                )
            # A %YAML 1.1 directive would turn plain yes/no/on into booleans.
            if event.version is not None or event.tags:
                raise YamlError("directives are not allowed", _line(event.start_mark))
        elif isinstance(event, AliasEvent):
            raise YamlError("aliases are not allowed", _line(event.start_mark))
        elif isinstance(event, NodeEvent) and event.anchor is not None:
            raise YamlError("anchors are not allowed", _line(event.start_mark))
        if (
            isinstance(event, ScalarEvent | CollectionStartEvent)
            and event.tag is not None
        ):
            raise YamlError("tags are not allowed", _line(event.start_mark))


def load_yaml(text: str) -> Any:
    """Parse one YAML 1.2 document into mappings and lists carrying line info.

    Raises `YamlError` on a syntax error, a duplicate key, an anchor, an alias,
    a tag or a second document. Plain `no`, `on` and `yes` stay strings.
    """
    try:
        _refuse_unsupported(text)
        return _reader().load(text)
    except MarkedYAMLError as error:
        mark = error.problem_mark or error.context_mark
        problem = error.problem or "invalid YAML"
        raise YamlError(problem, _line(mark)) from error
    except YAMLError as error:  # unreadable input, such as a control character
        raise YamlError("invalid YAML") from error


def key_line(mapping: Any, key: str) -> int | None:
    """1-based line of `key` in a mapping returned by `load_yaml`."""
    try:
        return int(mapping.lc.key(key)[0]) + 1
    except (AttributeError, KeyError):
        return None


def item_line(sequence: Any, index: int) -> int | None:
    """1-based line of item `index` in a list returned by `load_yaml`."""
    try:
        return int(sequence.lc.item(index)[0]) + 1
    except (AttributeError, KeyError, IndexError):
        return None


def node_line(node: Any) -> int | None:
    """1-based line where a mapping or list returned by `load_yaml` starts."""
    try:
        return int(node.lc.line) + 1
    except AttributeError:
        return None


@lru_cache(maxsize=4096)  # bounded: a long-running server writes many values
def _resolves_to_itself(text: str) -> bool:
    """Whether a YAML 1.2 reader reads `text` back as the same string."""
    try:
        reader = YAML(typ="safe")
        reader.version = (1, 2)
        return reader.load(text) == text
    except Exception:  # the text is not plain-safe, whatever the reason
        return False


def _is_plain(text: str) -> bool:
    """Whether `text` can be written unquoted and still read back as itself."""
    return (
        text != ""
        and text[0].isalnum()
        and text[-1] != " "
        and all(c.isalnum() or c in _PLAIN_CHARS for c in text)
        and text.lower() not in _YAML_11_BOOLEANS
        and _resolves_to_itself(text)
    )


def _quote(text: str) -> str:
    """Double-quote `text`, escaping what a YAML reader would mangle or refuse."""
    quoted = json.dumps(text, ensure_ascii=False)
    return "".join(
        c if c.isprintable() or ord(c) < 0x20 else f"\\U{ord(c):08x}" for c in quoted
    )


def _scalar(value: object) -> str:
    """A scalar as YAML text, quoted only when needed."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if math.isnan(value):
            return ".nan"
        if math.isinf(value):
            return ".inf" if value > 0 else "-.inf"
        return repr(value)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise TypeError("cannot write a datetime without a time zone")
        return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        return value if _is_plain(value) else _quote(value)
    raise TypeError(f"cannot write a {type(value).__name__} as a YAML scalar")


def _emit(lines: list[str], key: str, value: object, indent: int) -> None:
    """Append `key: value` to `lines`, nesting mappings and writing lists inline."""
    prefix = f"{' ' * indent}{_scalar(key)}:"
    if isinstance(value, Mapping):
        if not value:
            lines.append(f"{prefix} {{}}")
            return
        lines.append(prefix)
        for child_key, child in value.items():
            _emit(lines, child_key, child, indent + 2)
    elif isinstance(value, Sequence) and not isinstance(value, str):
        items = ", ".join(_scalar(item) for item in value)
        lines.append(f"{prefix} [{items}]")
    else:
        lines.append(f"{prefix} {_scalar(value)}")


def dump_yaml(data: Mapping[str, Any], *, separate_top_level: bool = False) -> str:
    """Write a mapping in canonical form, keys in the order given.

    Lists must hold scalars only; they are written in flow style. With
    `separate_top_level`, a blank line separates top-level entries.
    """
    lines: list[str] = []
    for key, value in data.items():
        if separate_top_level and lines:
            lines.append("")
        _emit(lines, key, value, 0)
    return "\n".join(lines) + "\n"
