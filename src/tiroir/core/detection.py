"""Detect the drawers a text names or the working directory points to (ADR-008).

Exact matching of each drawer's declared names on token boundaries, after the
normalisation of ADR-007 without stemming or stop words; the longest match
wins on overlaps; a name of several drawers is reported as an ambiguity and
detects none. A drawer is also matched from the folders of the working
directory. Nothing here guesses: only declared names and values match.
"""

import re
import sqlite3
import threading
from collections import defaultdict
from collections.abc import Collection, Iterable, Mapping, Sequence
from contextlib import closing
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from tiroir.core.index import index_path
from tiroir.core.layout import slug
from tiroir.core.lexical import DrawerRef
from tiroir.core.textnorm import fold

_TOKEN = re.compile(r"[^\W_]+")
_FOLDER_SEPARATORS = re.compile(r"[/\\]")
_DRIVE = re.compile(r"[A-Za-z]:")


@dataclass(frozen=True)
class Detection:
    """A drawer found, with the text that matched as the input wrote it."""

    drawer: DrawerRef
    matched: str
    via: Literal["name", "cwd"]


@dataclass(frozen=True)
class Ambiguity:
    """A name (or folder) shared by several drawers: reported, never chosen."""

    matched: str
    candidates: tuple[DrawerRef, ...]
    via: Literal["name", "cwd"]


@dataclass(frozen=True)
class NameDictionary:
    """The names of one store as token n-grams, and its `detect.cwd` values.

    `names` maps a name's tokens to the drawers declaring it; `cwd` maps a
    field to its slugified values and the drawers holding them.
    """

    store: str
    names: Mapping[tuple[str, ...], frozenset[DrawerRef]] = field(default_factory=dict)
    cwd: Mapping[str, Mapping[str, frozenset[DrawerRef]]] = field(default_factory=dict)

    @classmethod
    def build(
        cls,
        store: str,
        names: Iterable[tuple[str, str]],
        cwd_values: Iterable[tuple[str, str, str]] = (),
    ) -> "NameDictionary":
        """From `(drawer, name)` pairs and `(drawer, field, value)` triples."""
        by_tokens: dict[tuple[str, ...], set[DrawerRef]] = defaultdict(set)
        for drawer, name in names:
            tokens = tuple(name_tokens(name))
            if tokens:
                by_tokens[tokens].add(DrawerRef(store, drawer))
        by_field: dict[str, dict[str, set[DrawerRef]]] = defaultdict(
            lambda: defaultdict(set)
        )
        for drawer, field_name, value in cwd_values:
            if folder_slug := slug(value):
                by_field[field_name][folder_slug].add(DrawerRef(store, drawer))
        return cls(
            store,
            {key: frozenset(refs) for key, refs in by_tokens.items()},
            {
                name: {key: frozenset(refs) for key, refs in values.items()}
                for name, values in by_field.items()
            },
        )

    @property
    def longest(self) -> int:
        """The token count of the longest name, 0 for an empty dictionary."""
        return max((len(key) for key in self.names), default=0)


def _spans(text: str) -> list[tuple[str, int, int]]:
    """The tokens of `text` with the span of the written token each comes from.

    Folding can change a token's length or split it, so tokens are taken from
    each written token and keep that token's span.
    """
    found: list[tuple[str, int, int]] = []
    for written in _TOKEN.finditer(text):
        found += [
            (token, written.start(), written.end())
            for token in _TOKEN.findall(fold(written.group()))
        ]
    return found


def name_tokens(text: str) -> list[str]:
    """The tokens of a name or a text: folded, punctuation as boundaries.

    No stemming and no stop words (ADR-008): `Boulangerie-Dupont` gives
    `["boulangerie", "dupont"]`.
    """
    return [token for token, _, _ in _spans(text)]


@dataclass(frozen=True)
class _Match:
    start: int  # token index
    length: int  # in tokens
    candidates: frozenset[DrawerRef]


def _matches(
    tokens: Sequence[str], dictionaries: Sequence[NameDictionary]
) -> list[_Match]:
    """Every n-gram of `tokens` that is a declared name."""
    longest = max((d.longest for d in dictionaries), default=0)
    found: list[_Match] = []
    for start in range(len(tokens)):
        for length in range(min(longest, len(tokens) - start), 0, -1):
            key = tuple(tokens[start : start + length])
            refs = frozenset().union(*(d.names.get(key, ()) for d in dictionaries))
            if refs:
                found.append(_Match(start, length, refs))
    return found


def _longest_first(matches: list[_Match]) -> list[_Match]:
    """The matches kept on overlaps: longer first, then the leftmost."""
    kept: list[_Match] = []
    taken: set[int] = set()
    for match in sorted(matches, key=lambda m: (-m.length, m.start)):
        span = range(match.start, match.start + match.length)
        if taken.isdisjoint(span):
            taken.update(span)
            kept.append(match)
    return sorted(kept, key=lambda m: m.start)


def _folders(cwd: str) -> list[str]:
    """The folder names of a POSIX or Windows path, outermost first."""
    parts = [p for p in _FOLDER_SEPARATORS.split(cwd) if p.strip()]
    return [p for p in parts if not _DRIVE.fullmatch(p)]


def _by_cwd(
    cwd: str,
    dictionaries: Sequence[NameDictionary],
    cwd_fields: Mapping[str, Collection[str]],
) -> Detection | Ambiguity | None:
    """The drawer of the deepest folder of `cwd` that a `detect.cwd` value names."""
    for folder in reversed(_folders(cwd)):
        folder_slug = slug(folder)
        if not folder_slug:
            continue
        refs: set[DrawerRef] = set()
        for dictionary in dictionaries:
            for field_name in cwd_fields.get(dictionary.store, ()):
                refs |= dictionary.cwd.get(field_name, {}).get(folder_slug, set())
        if len(refs) == 1:
            return Detection(next(iter(refs)), folder, "cwd")
        if refs:
            return Ambiguity(folder, _ordered(refs), "cwd")
    return None


def _ordered(refs: Iterable[DrawerRef]) -> tuple[DrawerRef, ...]:
    """Drawer refs in a stable order."""
    return tuple(sorted(refs, key=lambda r: (r.store, r.drawer)))


def detect(
    text: str,
    cwd: str | None,
    dictionaries: Sequence[NameDictionary],
    cwd_fields: Mapping[str, Collection[str]],
) -> tuple[tuple[Detection, ...], tuple[Ambiguity, ...]]:
    """The drawers `text` names and `cwd` points to, and the ambiguities.

    `cwd_fields` gives, per store, the fields its types declare under
    `detect.cwd`. A drawer is detected once, a name match winning over the
    working directory.
    """
    spans = _spans(text)
    tokens = [token for token, _, _ in spans]
    detections: dict[DrawerRef, Detection] = {}
    ambiguities: dict[tuple[DrawerRef, ...], Ambiguity] = {}
    for match in _longest_first(_matches(tokens, dictionaries)):
        first, last = spans[match.start], spans[match.start + match.length - 1]
        written = text[first[1] : last[2]]
        if len(match.candidates) == 1:
            ref = next(iter(match.candidates))
            detections.setdefault(ref, Detection(ref, written, "name"))
        else:
            candidates = _ordered(match.candidates)
            ambiguities.setdefault(candidates, Ambiguity(written, candidates, "name"))
    by_cwd = _by_cwd(cwd, dictionaries, cwd_fields) if cwd else None
    if isinstance(by_cwd, Detection):
        detections.setdefault(by_cwd.drawer, by_cwd)
    elif by_cwd is not None:
        ambiguities.setdefault(by_cwd.candidates, by_cwd)
    return tuple(detections.values()), tuple(ambiguities.values())


# One dictionary per (index file, cwd fields), valid for the commit it was read at.
_cache: dict[tuple[str, frozenset[str]], tuple[str, NameDictionary]] = {}
_cache_lock = threading.Lock()


def _recorded_commit(db: sqlite3.Connection) -> str | None:
    """The commit the index was built from, `None` when it records none."""
    try:
        row = db.execute("SELECT value FROM meta WHERE key = 'commit'").fetchone()
    except sqlite3.OperationalError:
        return None
    return None if row is None else str(row[0])


def load_dictionary(
    data_dir: Path, store: str, store_id: str, cwd_fields: Collection[str] = ()
) -> NameDictionary:
    """The names and `detect.cwd` values of a store, read from its index.

    The index is opened read-only. The result is cached per store and read
    again when the index's recorded commit changes. A store with no index
    gives an empty dictionary.
    """
    path = index_path(data_dir, store_id)
    fields = frozenset(cwd_fields)
    if not path.exists():
        return NameDictionary(store)
    key = (f"{path}\0{store}", fields)
    with closing(sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True)) as db:
        commit = _recorded_commit(db)
        if commit is None:
            return NameDictionary(store)
        with _cache_lock:
            cached = _cache.get(key)
        if cached is not None and cached[0] == commit:
            return cached[1]
        names = db.execute("SELECT drawer, name FROM names").fetchall()
        marks = ", ".join("?" for _ in fields)
        values = db.execute(
            f"SELECT drawer, field, value FROM metadata WHERE field IN ({marks})",
            sorted(fields),
        ).fetchall()
    dictionary = NameDictionary.build(store, names, values)
    with _cache_lock:
        _cache[key] = (commit, dictionary)
    return dictionary
