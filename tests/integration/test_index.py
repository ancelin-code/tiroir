"""The per-store SQLite index: building, updating and rebuilding."""

import sqlite3
from contextlib import closing
from pathlib import Path

import pygit2

from tiroir.core.index import SCHEMA_HASH, index_path, index_store, rebuild
from tiroir.core.store import Author, StoreReader, append_log


def rows(data_dir: Path, store_id: str, sql: str) -> list[tuple[object, ...]]:
    """Rows of a query on the store's index."""
    with closing(sqlite3.connect(index_path(data_dir, store_id))) as db:
        return db.execute(sql).fetchall()


def test_first_run_indexes_the_drawers_and_the_shared_space(
    data_dir: Path, store_id: str
) -> None:
    # Given
    reader = StoreReader(data_dir, store_id)
    expected = [
        path
        for path in reader.files()
        if path.startswith(("clients/", "shared/")) and path.endswith(".md")
    ]

    # When
    report = index_store(data_dir, store_id)

    # Then
    assert report.rebuilt
    assert report.files_indexed == len(expected)
    assert report.chunks > report.files_indexed
    assert rows(data_dir, store_id, "SELECT path FROM files ORDER BY path") == [
        (path,) for path in expected
    ]
    assert rows(data_dir, store_id, "SELECT value FROM meta WHERE key='commit'") == [
        (report.commit,)
    ]
    assert index_path(data_dir, store_id).parent == data_dir / "index"


def test_index_is_in_wal_mode(data_dir: Path, store_id: str) -> None:
    # Given
    index_store(data_dir, store_id)

    # When
    mode = rows(data_dir, store_id, "PRAGMA journal_mode")

    # Then
    assert mode == [("wal",)]


def test_second_run_without_commit_does_nothing(data_dir: Path, store_id: str) -> None:
    # Given
    first = index_store(data_dir, store_id)

    # When
    second = index_store(data_dir, store_id)

    # Then
    assert not second.rebuilt
    assert second.files_indexed == 0
    assert second.chunks == first.chunks


def test_new_commit_indexes_only_the_new_file(
    data_dir: Path, store_id: str, author: Author
) -> None:
    # Given
    first = index_store(data_dir, store_id)
    append_log(data_dir, store_id, "clients/c001", "Nouvelle relance.", author)

    # When
    report = index_store(data_dir, store_id)

    # Then
    assert not report.rebuilt
    assert report.files_indexed == 1
    assert report.chunks == first.chunks + 1


def remove_file(data_dir: Path, store_id: str, path: str) -> None:
    """Commit the removal of a file on `main`, as a plain Git client would."""
    repo = StoreReader(data_dir, store_id).repo
    parent = repo.references["refs/heads/main"].peel(pygit2.Commit)
    tree = pygit2.Index()
    tree.read_tree(parent.tree)
    tree.remove(path)
    signature = pygit2.Signature("Test", "test@tiroir.invalid")
    repo.create_commit(
        "refs/heads/main",
        signature,
        signature,
        "remove",
        tree.write_tree(repo),
        [parent.id],
    )


def test_deleted_file_leaves_the_index(data_dir: Path, store_id: str) -> None:
    # Given
    index_store(data_dir, store_id)
    path = "clients/c001/log/2026/08/2026-08-12T124315Z-sofia-ijdr.md"
    remove_file(data_dir, store_id, path)

    # When
    report = index_store(data_dir, store_id)

    # Then
    assert report.files_removed == 1
    assert not report.rebuilt
    assert rows(data_dir, store_id, f"SELECT 1 FROM files WHERE path='{path}'") == []
    assert rows(data_dir, store_id, f"SELECT 1 FROM chunks WHERE path='{path}'") == []
    assert rows(data_dir, store_id, "SELECT count(*) FROM fts") == rows(
        data_dir, store_id, "SELECT count(*) FROM chunks"
    )


def test_drawer_metadata_and_names_are_stored(data_dir: Path, store_id: str) -> None:
    # Given
    index_store(data_dir, store_id)

    # When
    legal_form = rows(
        data_dir,
        store_id,
        "SELECT value FROM metadata WHERE drawer='clients/c001' AND field='legal_form'",
    )
    names = rows(
        data_dir, store_id, "SELECT name FROM names WHERE drawer='clients/c001'"
    )

    # Then
    assert legal_form == [("SARL",)]
    assert ("c001",) in names
    assert ("berenger",) in names


def test_schema_hash_mismatch_rebuilds(data_dir: Path, store_id: str) -> None:
    # Given
    index_store(data_dir, store_id)
    with closing(sqlite3.connect(index_path(data_dir, store_id))) as db:
        db.execute("UPDATE meta SET value='stale' WHERE key='schema_hash'")
        db.commit()

    # When
    report = index_store(data_dir, store_id)

    # Then
    assert report.rebuilt
    assert rows(
        data_dir, store_id, "SELECT value FROM meta WHERE key='schema_hash'"
    ) == [(SCHEMA_HASH,)]


def test_rebuild_after_deleting_the_file_gives_the_same_index(
    data_dir: Path, store_id: str, author: Author
) -> None:
    # Given
    append_log(data_dir, store_id, "clients/c001", "Relance du 5.", author)
    index_store(data_dir, store_id)
    sql = "SELECT path, ord, section, date, author, text FROM chunks ORDER BY path, ord"
    before = rows(data_dir, store_id, sql)
    index_path(data_dir, store_id).unlink()

    # When
    report = rebuild(data_dir, store_id)

    # Then
    assert report.rebuilt
    assert rows(data_dir, store_id, sql) == before


def test_rebuild_over_an_index_file_without_tables(
    data_dir: Path, store_id: str
) -> None:
    # Given
    path = index_path(data_dir, store_id)
    path.parent.mkdir(parents=True)
    sqlite3.connect(path).close()

    # When
    report = rebuild(data_dir, store_id)

    # Then
    assert report.rebuilt
    assert report.chunks > 0


def test_rebuild_in_place_gives_the_same_index(data_dir: Path, store_id: str) -> None:
    # Given
    index_store(data_dir, store_id)
    sql = "SELECT path, ord, section, text FROM chunks ORDER BY path, ord"
    before = rows(data_dir, store_id, sql)

    # When
    report = rebuild(data_dir, store_id)

    # Then
    assert report.rebuilt
    assert rows(data_dir, store_id, sql) == before
