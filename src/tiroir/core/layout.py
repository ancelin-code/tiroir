"""The shapes of a store's files and commits (contract `store-layout.md`).

Pure functions: slugs, drawer paths, log entry names, frontmatter in
canonical form, `MEMORY.md` and commit messages. Reading and writing the
repository is `tiroir.core.store`'s.
"""

import re
import secrets
import string
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from tiroir.core.errors import CoreError
from tiroir.core.schema import METADATA_INVALID, DrawerType, Schema
from tiroir.core.yaml_io import YamlError, dump_yaml, load_yaml

SCHEMA_FILE = "tiroir.yaml"
MEMORY_FILE = "MEMORY.md"
SUMMARY_FILE = "summary.md"
SLUG_MAX = 64
SUFFIX_ALPHABET = string.ascii_lowercase + string.digits

_PLACEHOLDER = re.compile(r"\{([^{}]*)\}")
_SLUG_SHAPE = r"[a-z0-9]+(?:-[a-z0-9]+)*"
_FRONTMATTER = re.compile(r"\A---\n(.*?\n)?---\n", re.DOTALL)

# What MEMORY.md says, per store language; English for any other language.
_MEMORY_TEXT = {
    "en": (
        "Each drawer is a folder holding `summary.md`, its summary, and `log/`, "
        "its dated log entries. Shared documents are under `{shared}/`."
    ),
    "fr": (
        "Chaque tiroir est un dossier qui contient `summary.md`, sa fiche, et "
        "`log/`, son journal daté. Les documents partagés sont dans `{shared}/`."
    ),
}


@dataclass(frozen=True)
class Drawer:
    """A drawer found in a store: its id, type name and summary frontmatter."""

    id: str
    type: str
    fields: Mapping[str, Any]


def slug(text: str) -> str:
    """The contract's slug: no diacritics, lowercase, `[a-z0-9-]`, 64 at most."""
    decomposed = unicodedata.normalize("NFKD", unicodedata.normalize("NFKC", text))
    bare = "".join(c for c in decomposed if not unicodedata.combining(c))
    dashed = re.sub(r"[^a-z0-9]+", "-", bare.lower()).strip("-")
    return dashed[:SLUG_MAX].rstrip("-")


def _text(value: object) -> str:
    """A field value as plain text: lists joined, dates in ISO form."""
    if isinstance(value, str):
        return value
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Iterable):
        return ", ".join(_text(item) for item in value)
    return str(value)


def drawer_path(drawer_type: DrawerType, fields: Mapping[str, object]) -> str:
    """The drawer's folder: the type's pattern with each placeholder slugged.

    Raises `metadata.invalid` when a placeholder's value is missing or slugs
    to nothing.
    """

    def fill(match: re.Match[str]) -> str:
        """The slug of the placeholder's value."""
        name = match.group(1)
        value = fields.get(name)
        filled = "" if value is None else slug(_text(value))
        if not filled:
            raise CoreError(
                METADATA_INVALID, f"field {name} gives an empty drawer folder name"
            )
        return filled

    return _PLACEHOLDER.sub(fill, drawer_type.path)


def drawer_pattern(drawer_type: DrawerType) -> re.Pattern[str]:
    """A regular expression matching the drawer ids the type's pattern produces."""
    parts = _PLACEHOLDER.split(drawer_type.path)
    # split() alternates literal text and placeholder names.
    regex = "".join(
        re.escape(part) if i % 2 == 0 else _SLUG_SHAPE for i, part in enumerate(parts)
    )
    return re.compile(regex)


def new_suffix() -> str:
    """Four random characters of `[a-z0-9]` for a log entry name."""
    return "".join(secrets.choice(SUFFIX_ALPHABET) for _ in range(4))


def log_entry_path(drawer_id: str, when: datetime, author: str, suffix: str) -> str:
    """`<drawer>/log/<yyyy>/<mm>/<yyyy-mm-dd>T<hhmmss>Z-<author>-<rand>.md`, in UTC."""
    utc = when.astimezone(UTC)
    name = f"{utc:%Y-%m-%dT%H%M%S}Z-{author}-{suffix}.md"
    return f"{drawer_id}/log/{utc:%Y}/{utc:%m}/{name}"


def render_frontmatter(data: Mapping[str, Any]) -> str:
    """A frontmatter block in canonical form, keys in the order given."""
    return f"---\n{dump_yaml(data)}---\n"


def split_frontmatter(text: str) -> tuple[str | None, str]:
    """The frontmatter's YAML text (`None` when there is none) and the body."""
    match = _FRONTMATTER.match(text)
    if match is None:
        return None, text
    return match.group(1) or "", text[match.end() :]


def render_log_entry(when: datetime, author: str, body: str) -> str:
    """A log entry file: `date` and `author` frontmatter, then the body."""
    text = body if body.endswith("\n") else body + "\n"
    return render_frontmatter({"date": when, "author": author}) + text


def _fill_template(
    template: str, drawer_type: DrawerType, fields: Mapping[str, object]
) -> str:
    """The template with each `{field}` of a declared field replaced by its value."""

    def fill(match: re.Match[str]) -> str:
        """The field's value as text, empty when absent; others left as written."""
        name = match.group(1)
        if name not in drawer_type.fields:
            return match.group(0)
        value = fields.get(name)
        return "" if value is None else _text(value)

    return _PLACEHOLDER.sub(fill, template)


def render_summary(
    type_name: str,
    drawer_type: DrawerType,
    fields: Mapping[str, object],
    template: str,
) -> str:
    """A new `summary.md`: `type` then the fields in schema order, then the template."""
    data: dict[str, Any] = {"type": type_name}
    data.update({n: fields[n] for n in drawer_type.fields if fields.get(n) is not None})
    return render_frontmatter(data) + _fill_template(template, drawer_type, fields)


def drawers_in(schema: Schema, summaries: Mapping[str, str]) -> list[Drawer]:
    """The drawers among `summary.md` texts keyed by path, sorted by drawer id.

    A summary counts when its folder matches a drawer type's pattern. Raises
    `metadata.invalid` when such a summary's frontmatter is not readable.
    """
    patterns = {name: drawer_pattern(t) for name, t in schema.drawer_types.items()}
    drawers: list[Drawer] = []
    for path, text in summaries.items():
        folder, _, file_name = path.rpartition("/")
        if file_name != SUMMARY_FILE:
            continue
        type_name = next((n for n, p in patterns.items() if p.fullmatch(folder)), None)
        if type_name is None:
            continue
        yaml_text, _ = split_frontmatter(text)
        try:
            fields = load_yaml(yaml_text or "{}")
        except YamlError as error:
            raise CoreError(
                METADATA_INVALID, f"{path}: unreadable frontmatter"
            ) from error
        if not isinstance(fields, Mapping):
            raise CoreError(METADATA_INVALID, f"{path}: frontmatter is not a mapping")
        drawers.append(Drawer(folder, type_name, fields))
    return sorted(drawers, key=lambda d: d.id)


def _drawer_names(drawer_type: DrawerType, drawer: Drawer) -> str:
    """The names a drawer is known by: its detect names, else its path fields."""
    if drawer_type.detect is not None and drawer_type.detect.names is not None:
        names = drawer_type.detect.names
    else:
        names = tuple(_PLACEHOLDER.findall(drawer_type.path))
    values = [drawer.fields.get(n) for n in names]
    return ", ".join(_text(v) for v in values if v is not None and _text(v))


def render_memory(schema: Schema, drawers: Iterable[Drawer]) -> str:
    """`MEMORY.md`: the store, its layout, then one line per drawer by type."""
    store = schema.store
    lines = [f"# {store.name}", ""]
    if store.description:
        lines += [store.description, ""]
    explanation = _MEMORY_TEXT.get(store.language, _MEMORY_TEXT["en"])
    lines += [explanation.format(shared=schema.shared_path), ""]
    by_type: dict[str, list[Drawer]] = {}
    for drawer in drawers:
        by_type.setdefault(drawer.type, []).append(drawer)
    for type_name, drawer_type in schema.drawer_types.items():
        members = sorted(by_type.get(type_name, []), key=lambda d: d.id)
        if not members:
            continue
        lines += [f"## {drawer_type.label_plural or drawer_type.label}", ""]
        for drawer in members:
            names = _drawer_names(drawer_type, drawer)
            label = f"{drawer_type.label}: {names}" if names else drawer_type.label
            lines.append(f"- [[{drawer.id}/summary]] — {label}")
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


def commit_message(
    op: str, author: str, via: str, drawer: str | None = None, target: str = "store"
) -> str:
    """A commit message: the subject, then the contract's trailers.

    The subject names the drawer when there is one, else `target` (`store` or
    `shared`); nothing else, so no memory content reaches the history (Y5).
    """
    trailers = [f"Tiroir-Op: {op}"]
    if drawer is not None:
        trailers.append(f"Tiroir-Drawer: {drawer}")
    trailers += [f"Tiroir-Author: {author}", f"Tiroir-Via: {via}"]
    subject = f"tiroir: {op} {drawer if drawer is not None else target}"
    return subject + "\n\n" + "\n".join(trailers) + "\n"
