"""The per-store SQLite index, derived from the commits of `main` (ADR-005).

One file per store at `<data>/index/<store-id>.sqlite`, in WAL mode: files,
chunks, drawer metadata, drawer names, and an FTS5 table whose rowid is the
chunk id, with a `text` column (normalised, stemmed) and an `ids` column
(identifier tokens). The indexer is the only writer. Vectors will be one more
table keyed by chunk id; nothing here depends on them.
"""

import hashlib
import re
import sqlite3
from collections.abc import Iterable, Iterator
from contextlib import closing, contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from tiroir.core import textnorm
from tiroir.core.chunking import (
    Chunk,
    Kind,
    log_chunks,
    shared_chunks,
    summary_chunks,
)
from tiroir.core.errors import CoreError
from tiroir.core.layout import (
    SCHEMA_FILE,
    SUMMARY_FILE,
    drawer_pattern,
    split_frontmatter,
)
from tiroir.core.schema import Schema
from tiroir.core.store import StoreReader
from tiroir.core.yaml_io import YamlError, load_yaml

_DDL = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE files (
    path TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    drawer TEXT,
    drawer_type TEXT
);
CREATE INDEX files_drawer ON files (drawer);
CREATE TABLE chunks (
    id INTEGER PRIMARY KEY,
    path TEXT NOT NULL REFERENCES files (path),
    ord INTEGER NOT NULL,
    section TEXT,
    date TEXT,
    author TEXT,
    text TEXT NOT NULL,
    UNIQUE (path, ord)
);
CREATE TABLE metadata (
    drawer TEXT NOT NULL,
    field TEXT NOT NULL,
    value TEXT NOT NULL,
    folded TEXT NOT NULL
);
CREATE INDEX metadata_drawer ON metadata (drawer, field, folded);
CREATE TABLE names (drawer TEXT NOT NULL, name TEXT NOT NULL);
CREATE INDEX names_drawer ON names (drawer);
CREATE VIRTUAL TABLE fts USING fts5(text, ids, tokenize = 'unicode61');
"""
_TABLES = ("fts", "names", "metadata", "chunks", "files", "meta")

# Changes with the tables or the normalisation, so a mismatch rebuilds the file.
SCHEMA_HASH = hashlib.sha256(f"{_DDL}{textnorm.VERSION}".encode()).hexdigest()[:16]

_BUSY_TIMEOUT_MS = 10_000
_PLACEHOLDER = re.compile(r"\{([^{}]*)\}")
_LOG_FOLDER = "/log/"


@dataclass(frozen=True)
class IndexReport:
    """What one `index_store` run did."""

    store_id: str
    commit: str
    files_indexed: int
    files_removed: int
    chunks: int
    rebuilt: bool


def index_path(data_dir: Path, store_id: str) -> Path:
    """`<data>/index/<store-id>.sqlite`, beside and never inside the repository."""
    return data_dir / "index" / f"{store_id}.sqlite"


def connect(path: Path) -> sqlite3.Connection:
    """A connection to an index file in WAL mode, with explicit transactions."""
    db = sqlite3.connect(path, isolation_level=None)
    db.execute(f"PRAGMA busy_timeout = {_BUSY_TIMEOUT_MS}")
    db.execute("PRAGMA journal_mode = WAL")
    return db


@contextmanager
def _transaction(db: sqlite3.Connection) -> Iterator[None]:
    """A write transaction: taken up front, committed or rolled back as a whole."""
    db.execute("BEGIN IMMEDIATE")
    try:
        yield
    except BaseException:
        db.execute("ROLLBACK")
        raise
    db.execute("COMMIT")


def _meta(db: sqlite3.Connection, key: str) -> str | None:
    """A value of the `meta` table, `None` when the table or the key is missing."""
    try:
        row = db.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    except sqlite3.OperationalError:
        return None
    return None if row is None else str(row[0])


def _wipe(db: sqlite3.Connection) -> None:
    """Drop every table and create them empty."""
    for table in _TABLES:
        db.execute(f"DROP TABLE IF EXISTS {table}")
    for statement in _DDL.split(";"):
        if statement.strip():
            db.execute(statement)


def _flatten(value: object) -> list[str]:
    """A metadata value as the strings it filters on: one per list item."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, datetime):
        return [value.date().isoformat()]
    if isinstance(value, date):
        return [value.isoformat()]
    if isinstance(value, Iterable):
        return [text for item in value for text in _flatten(item)]
    return [str(value)]


def _as_date(value: object) -> str | None:
    """The UTC calendar day of a frontmatter date, in ISO form."""
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = value.astimezone(UTC)
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return None


def _frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """The frontmatter mapping (empty when absent or unreadable) and the body."""
    yaml_text, body = split_frontmatter(text)
    try:
        data = load_yaml(yaml_text or "{}")
    except YamlError:
        return {}, body
    return (dict(data) if isinstance(data, dict) else {}), body


@dataclass(frozen=True)
class _Classified:
    """Where an indexed file belongs: its kind, drawer and drawer type."""

    kind: Kind
    drawer: str | None
    drawer_type: str | None


def _classify(schema: Schema, path: str) -> _Classified | None:
    """The kind, drawer and type of a file, `None` when it is not indexed."""
    if path.startswith(f"{schema.shared_path}/") and path.endswith(".md"):
        return _Classified(Kind.SHARED, None, None)
    for name, drawer_type in schema.drawer_types.items():
        pattern = drawer_pattern(drawer_type)
        folder, _, file_name = path.rpartition("/")
        if file_name == SUMMARY_FILE and pattern.fullmatch(folder):
            return _Classified(Kind.SUMMARY, folder, name)
        drawer, sep, _ = path.partition(_LOG_FOLDER)
        if sep and path.endswith(".md") and pattern.fullmatch(drawer):
            return _Classified(Kind.LOG, drawer, name)
    return None


def _names(schema: Schema, type_name: str, fields: dict[str, Any]) -> list[str]:
    """The names a drawer is known by: its detect names, else its path fields."""
    drawer_type = schema.drawer_types[type_name]
    if drawer_type.detect is not None and drawer_type.detect.names is not None:
        field_names: Iterable[str] = drawer_type.detect.names
    else:
        field_names = _PLACEHOLDER.findall(drawer_type.path)
    found = [t for n in field_names if n in fields for t in _flatten(fields[n])]
    return list(dict.fromkeys(textnorm.fold(t) for t in found if t.strip()))


def _remove(db: sqlite3.Connection, path: str) -> bool:
    """Forget a file with its chunks, and its drawer's metadata if a summary."""
    row = db.execute(
        "SELECT kind, drawer FROM files WHERE path = ?", (path,)
    ).fetchone()
    if row is None:
        return False
    db.execute(
        "DELETE FROM fts WHERE rowid IN (SELECT id FROM chunks WHERE path = ?)",
        (path,),
    )
    db.execute("DELETE FROM chunks WHERE path = ?", (path,))
    db.execute("DELETE FROM files WHERE path = ?", (path,))
    if row[0] == Kind.SUMMARY.value:
        db.execute("DELETE FROM metadata WHERE drawer = ?", (row[1],))
        db.execute("DELETE FROM names WHERE drawer = ?", (row[1],))
    return True


def _add(db: sqlite3.Connection, schema: Schema, path: str, data: bytes) -> int | None:
    """Index a file; returns its chunk count, `None` when it is not indexed."""
    where = _classify(schema, path)
    if where is None:
        return None
    language = schema.store.language
    fields, body = _frontmatter(data.decode("utf-8", errors="replace"))
    when: str | None = None
    author: str | None = None
    chunks: list[Chunk]
    if where.kind is Kind.SUMMARY:
        chunks = summary_chunks(body)
    elif where.kind is Kind.LOG:
        chunks = log_chunks(body)
        when = _as_date(fields.get("date"))
        author = str(fields["author"]) if "author" in fields else None
    else:
        chunks = shared_chunks(body)
    db.execute(
        "INSERT INTO files (path, kind, drawer, drawer_type) VALUES (?, ?, ?, ?)",
        (path, where.kind.value, where.drawer, where.drawer_type),
    )
    if where.kind is Kind.SUMMARY and where.drawer and where.drawer_type:
        db.executemany(
            "INSERT INTO metadata (drawer, field, value, folded) VALUES (?, ?, ?, ?)",
            [
                (where.drawer, name, text, textnorm.fold(text))
                for name, value in fields.items()
                for text in _flatten(value)
            ],
        )
        db.executemany(
            "INSERT INTO names (drawer, name) VALUES (?, ?)",
            [(where.drawer, n) for n in _names(schema, where.drawer_type, fields)],
        )
    for order, chunk in enumerate(chunks):
        indexed = f"{chunk.section or ''}\n{chunk.text}"
        cursor = db.execute(
            "INSERT INTO chunks (path, ord, section, date, author, text)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (path, order, chunk.section, when, author, chunk.text),
        )
        db.execute(
            "INSERT INTO fts (rowid, text, ids) VALUES (?, ?, ?)",
            (
                cursor.lastrowid,
                textnorm.normalize(indexed, language),
                " ".join(textnorm.identifier_tokens(indexed)),
            ),
        )
    return len(chunks)


def _count_chunks(db: sqlite3.Connection) -> int:
    """The number of chunks in the index."""
    return int(db.execute("SELECT count(*) FROM chunks").fetchone()[0])


def index_store(data_dir: Path, store_id: str) -> IndexReport:
    """Bring a store's index to the head of `main`, reading only what changed.

    Compares the commit recorded in the index with the head and re-indexes the
    files changed between them. The whole index is rebuilt when it is new, when
    its schema hash differs, when the recorded commit is not in the repository
    or when `tiroir.yaml` changed. Raises `store.unknown` or `schema.invalid`.
    """
    return _index(data_dir, store_id, force=False)


def rebuild(data_dir: Path, store_id: str) -> IndexReport:
    """Index the store from scratch, in one transaction readers do not see half of."""
    return _index(data_dir, store_id, force=True)


def _index(data_dir: Path, store_id: str, *, force: bool) -> IndexReport:
    """`index_store`, or with `force` a rebuild whatever the index records."""
    reader = StoreReader(data_dir, store_id)
    head = reader.head()
    schema = reader.schema(head)
    path = index_path(data_dir, store_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(connect(path)) as db:
        recorded = _meta(db, "commit")
        if force or _meta(db, "schema_hash") != SCHEMA_HASH:
            recorded = None
        if recorded == head:
            return IndexReport(store_id, head, 0, 0, _count_chunks(db), False)
        changed: list[str] | None = None
        if recorded is not None:
            try:
                changed = reader.changed_paths(recorded, head)
            except CoreError:
                changed = None
            if changed is not None and SCHEMA_FILE in changed:
                changed = None
        rebuilt = changed is None
        paths = reader.files(head) if changed is None else changed
        indexed = removed = 0
        with _transaction(db):
            if rebuilt:
                _wipe(db)
            for file in paths:
                existed = _remove(db, file)
                data = reader.read(file, head)
                if data is None:
                    removed += existed
                elif _add(db, schema, file, data) is not None:
                    indexed += 1
            values = {
                "commit": head,
                "schema_hash": SCHEMA_HASH,
                "store_id": store_id,
                "store_name": schema.store.name,
                "language": schema.store.language,
            }
            db.executemany(
                "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
                values.items(),
            )
        return IndexReport(store_id, head, indexed, removed, _count_chunks(db), rebuilt)
