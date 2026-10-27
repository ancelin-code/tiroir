"""Lexical search over the stores' indexes (ADR-007).

BM25 ranking from FTS5, filters applied inside the query so they come before
ranking (X1), the lexical admission floor, and exact identifier matches ranked
first. An empty result is an abstention: nothing cleared the floor.
"""

import math
import sqlite3
from collections.abc import Mapping, Sequence
from contextlib import closing
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Any

from loguru import logger

from tiroir.core import textnorm
from tiroir.core.chunking import Kind
from tiroir.core.index import index_path

CANDIDATES = 50
# Weight of the identifier column against the text column in BM25.
_IDS_WEIGHT = 10.0


class Channel(Enum):
    """The retrieval channel that found a hit."""

    LEXICAL = "lexical"
    VECTOR = "vector"
    IDENTIFIER = "identifier"


@dataclass(frozen=True)
class DrawerRef:
    """A drawer across stores: the store's name and the drawer id."""

    store: str
    drawer: str


@dataclass(frozen=True)
class Scope:
    """Which drawers a search may read (M5, X1, X2).

    No drawers and `all_drawers` false means the shared spaces only.
    """

    drawers: tuple[DrawerRef, ...] = ()
    all_drawers: bool = False


@dataclass(frozen=True)
class Filters:
    """Narrowing criteria; a criterion left empty does not narrow."""

    types: tuple[str, ...] = ()
    stores: tuple[str, ...] = ()
    fields: Mapping[str, str] = field(default_factory=dict)
    kinds: tuple[Kind, ...] = ()
    since: date | None = None
    until: date | None = None


@dataclass(frozen=True)
class Hit:
    """A chunk found by search, with where it comes from (R6)."""

    store: str
    drawer: str | None
    path: str
    kind: Kind
    section: str | None
    date: date | None
    author: str | None
    text: str
    score: float
    channels: tuple[Channel, ...]


def _quoted(words: Sequence[str]) -> str:
    """FTS5 phrases for the words, joined by OR."""
    return " OR ".join('"' + word.replace('"', '""') + '"' for word in words)


def _where(
    scope: Scope, filters: Filters, drawers: Sequence[str]
) -> tuple[str, list[str]]:
    """The SQL conditions and parameters for the scope and the filters."""
    conditions: list[str] = []
    params: list[str] = []
    if not scope.all_drawers:
        marks = ", ".join("?" for _ in drawers)
        conditions.append(f"(f.kind = 'shared' OR f.drawer IN ({marks}))")
        params += drawers
    if filters.types:
        conditions.append(f"f.drawer_type IN ({', '.join('?' for _ in filters.types)})")
        params += filters.types
    if filters.kinds:
        conditions.append(f"f.kind IN ({', '.join('?' for _ in filters.kinds)})")
        params += [kind.value for kind in filters.kinds]
    for name, value in filters.fields.items():
        conditions.append(
            "EXISTS (SELECT 1 FROM metadata m"
            " WHERE m.drawer = f.drawer AND m.field = ? AND m.folded = ?)"
        )
        params += [name, textnorm.fold(value)]
    if filters.since is not None:
        conditions.append("c.date >= ?")
        params.append(filters.since.isoformat())
    if filters.until is not None:
        conditions.append("c.date <= ?")
        params.append(filters.until.isoformat())
    return "".join(f" AND {c}" for c in conditions), params


@dataclass(frozen=True)
class _Candidate:
    """A chunk that matched, before the floor."""

    hit: Hit
    exact: bool
    order: int


def _search_index(
    db: sqlite3.Connection,
    query: str,
    scope: Scope,
    filters: Filters,
) -> list[_Candidate]:
    """The admitted candidates of one store, best first; empty when it abstains."""
    try:
        meta = dict(db.execute("SELECT key, value FROM meta").fetchall())
    except sqlite3.OperationalError:
        return []  # the index is being created
    if "store_name" not in meta:
        return []
    name, language = meta["store_name"], meta["language"]
    if filters.stores and name not in filters.stores:
        return []
    drawers = [d.drawer for d in scope.drawers if d.store == name]
    if scope.drawers and not scope.all_drawers and not drawers:
        return []
    query_terms = list(dict.fromkeys(textnorm.terms(query, language)))
    query_ids = textnorm.identifier_tokens(query, query=True)
    if not query_terms and not query_ids:
        return []
    conditions, params = _where(scope, filters, drawers)
    sql = (
        f"SELECT c.id, c.ord, f.path, f.kind, f.drawer, c.section, c.date, c.author,"
        f" c.text, fts.text, fts.ids, bm25(fts, 1.0, {_IDS_WEIGHT})"
        " FROM fts JOIN chunks c ON c.id = fts.rowid JOIN files f ON f.path = c.path"
        f" WHERE fts MATCH ?{conditions} ORDER BY 12 LIMIT {CANDIDATES}"
    )
    parts: list[str] = []
    if query_terms:
        parts.append(f"text : ({_quoted(query_terms)})")
    if query_ids:
        parts.append(f"ids : ({_quoted(query_ids)})")
    matches = [" OR ".join(parts)]
    if query_ids and query_terms:
        # Exact identifiers must be candidates however the text ranks.
        matches.append(f"ids : ({_quoted(query_ids)})")
    rows: dict[int, tuple[Any, ...]] = {}
    for match in matches:
        for row in db.execute(sql, [match, *params]):
            rows.setdefault(row[0], row)
    needed = max(1, math.ceil(len(query_terms) / 2))
    wanted = set(query_ids)
    found: list[_Candidate] = []
    for row in rows.values():
        (
            _,
            order,
            path,
            kind,
            drawer,
            section,
            when,
            author,
            text,
            indexed,
            ids,
            bm25,
        ) = row
        exact = bool(wanted.intersection(str(ids).split()))
        matched = len(set(query_terms).intersection(str(indexed).split()))
        if not exact and (not query_terms or matched < needed):
            continue
        channels = (
            (Channel.LEXICAL, Channel.IDENTIFIER) if exact else (Channel.LEXICAL,)
        )
        hit = Hit(
            store=name,
            drawer=None if drawer is None else str(drawer),
            path=str(path),
            kind=Kind(kind),
            section=None if section is None else str(section),
            date=None if when is None else date.fromisoformat(str(when)),
            author=None if author is None else str(author),
            text=str(text),
            score=-float(bm25),
            channels=channels,
        )
        found.append(_Candidate(hit, exact, int(order)))
    return found


def search_lexical(
    data_dir: Path,
    store_ids: Sequence[str],
    query: str,
    scope: Scope,
    filters: Filters | None = None,
    limit: int = 10,
) -> list[Hit]:
    """Hits for the query in the stores' indexes, best first; `[]` is an abstention.

    The scope and the filters narrow the candidates before ranking. A chunk is
    admitted when it matches an identifier of the query exactly or at least
    half of the query's content terms (one at least); chunks matching an
    identifier come first, then by BM25 score. Stores without an index, or
    with an unreadable one (logged), are skipped. Scores of different stores
    are only roughly comparable.
    """
    filters = filters or Filters()
    found: list[_Candidate] = []
    for store_id in store_ids:
        path = index_path(data_dir, store_id)
        if not path.exists():
            continue
        try:
            with closing(sqlite3.connect(path)) as db:
                found += _search_index(db, query, scope, filters)
        except sqlite3.DatabaseError:
            logger.error("index of store {} is unreadable, skipped", store_id)
    found.sort(key=lambda c: (not c.exact, -c.hit.score, c.hit.path, c.order))
    return [candidate.hit for candidate in found[:limit]]
