"""The background indexer."""

import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from tiroir.core.index import index_path
from tiroir.core.indexer import Indexer
from tiroir.core.lexical import Hit, Scope, search_lexical
from tiroir.core.store import Author, append_log

EVERYWHERE = Scope(all_drawers=True)


@pytest.fixture
def indexer(data_dir: Path) -> Iterator[Indexer]:
    """A started indexer over the data directory, stopped afterwards."""
    running = Indexer(data_dir)
    running.start()
    yield running
    running.stop()


def test_start_indexes_the_existing_stores(
    data_dir: Path, store_id: str, indexer: Indexer
) -> None:
    # Given
    path = index_path(data_dir, store_id)

    # When
    idle = indexer.wait_idle(timeout=30)

    # Then
    assert idle
    assert path.exists()
    assert search_lexical(data_dir, [store_id], "tva", EVERYWHERE)


def test_new_entry_is_searchable_within_two_seconds(
    data_dir: Path, store_id: str, author: Author, indexer: Indexer
) -> None:
    # Given
    assert indexer.wait_idle(timeout=30)
    started = time.monotonic()

    # When
    append_log(data_dir, store_id, "clients/c001", "Dossier zébulon ouvert.", author)
    indexer.submit(store_id)
    hits: list[Hit] = []
    while not hits and time.monotonic() - started < 5:
        hits = search_lexical(data_dir, [store_id], "zebulon", EVERYWHERE)
        time.sleep(0.01)
    elapsed = time.monotonic() - started

    # Then
    assert hits
    assert elapsed < 2


def test_unknown_store_job_is_dropped(
    data_dir: Path, store_id: str, indexer: Indexer
) -> None:
    # Given
    assert indexer.wait_idle(timeout=30)

    # When
    indexer.submit("absent")
    indexer.submit("absent")
    idle = indexer.wait_idle(timeout=10)

    # Then
    assert idle


def test_failing_job_does_not_stop_the_indexer(
    data_dir: Path, store_id: str, author: Author, indexer: Indexer
) -> None:
    # Given
    assert indexer.wait_idle(timeout=30)
    indexer.submit("absent")
    append_log(data_dir, store_id, "clients/c001", "Après l'échec.", author)

    # When
    indexer.submit(store_id)
    idle = indexer.wait_idle(timeout=10)

    # Then
    assert idle
    assert search_lexical(data_dir, [store_id], "echec", EVERYWHERE)
