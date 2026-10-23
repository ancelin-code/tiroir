"""The per-store write lock, across threads and processes."""

import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from tiroir.core.errors import CoreError
from tiroir.core.locks import LOCK_TIMEOUT, lock_path, store_lock
from tiroir.core.store import Author, StoreReader, append_log, create_store

STORE_ID = "0d6c1e9a-0000-4000-8000-000000000001"
ALICE = Author("alice", "Alice Martin", "cli")
SCHEMA = f"""\
tiroir: 1
store:
  id: {STORE_ID}
  name: notes
  audience: personal
  language: en
drawer_types:
  project:
    label: Project
    path: "projects/{{name}}"
    fields:
      name: {{type: text, required: true}}
    summary:
      template: templates/project.md
      sections: [Goal]
"""
HOLDER = """
import fcntl, sys, time
with open(sys.argv[1], "a") as file:
    fcntl.flock(file, fcntl.LOCK_EX)
    print("held", flush=True)
    time.sleep(float(sys.argv[2]))
"""


@pytest.fixture
def store(tmp_path: Path) -> Path:
    """A data directory holding a small store with one drawer."""
    files = {
        "tiroir.yaml": SCHEMA.encode(),
        "templates/project.md": b"## Goal\n",
        "projects/site/summary.md": b"---\ntype: project\nname: site\n---\n## Goal\n",
    }
    create_store(tmp_path, STORE_ID, files, ALICE)
    return tmp_path


def hold_in_process(data_dir: Path, seconds: float) -> subprocess.Popen[str]:
    """Start a process holding the store's lock for `seconds`, once it holds it."""
    path = lock_path(data_dir, STORE_ID)
    path.parent.mkdir(parents=True, exist_ok=True)
    process = subprocess.Popen(
        [sys.executable, "-c", HOLDER, str(path), str(seconds)],
        stdout=subprocess.PIPE,
        text=True,
    )
    assert process.stdout is not None
    assert process.stdout.readline() == "held\n"
    return process


def test_the_lock_waits_ten_seconds_by_default() -> None:
    # Given
    # the timeout ADR-009 and ADR-010 set

    # When
    timeout = LOCK_TIMEOUT

    # Then
    assert timeout == 10.0


def test_lock_held_by_another_process_makes_the_write_busy(store: Path) -> None:
    # Given
    head = StoreReader(store, STORE_ID).head()
    holder = hold_in_process(store, 5)

    # When
    started = time.monotonic()
    with pytest.raises(CoreError) as caught:
        append_log(store, STORE_ID, "projects/site", "Text.", ALICE, lock_timeout=0.5)
    waited = time.monotonic() - started

    # Then
    holder.kill()
    holder.wait()
    assert caught.value.code == "store.busy"
    assert waited >= 0.5
    assert StoreReader(store, STORE_ID).head() == head


def test_lock_held_more_than_ten_seconds_makes_the_write_busy(store: Path) -> None:
    # Given
    # a lock held past the default timeout; this test takes ten seconds
    holder = hold_in_process(store, 15)

    # When
    started = time.monotonic()
    with pytest.raises(CoreError) as caught:
        append_log(store, STORE_ID, "projects/site", "Text.", ALICE)
    waited = time.monotonic() - started

    # Then
    holder.kill()
    holder.wait()
    assert caught.value.code == "store.busy"
    assert 10.0 <= waited < 12.0


def test_lock_held_by_another_thread_makes_the_lock_busy(tmp_path: Path) -> None:
    # Given
    held, release = threading.Event(), threading.Event()

    def hold() -> None:
        """Hold the lock until told to release it."""
        with store_lock(tmp_path, STORE_ID):
            held.set()
            release.wait()

    thread = threading.Thread(target=hold)
    thread.start()
    held.wait()

    # When
    with pytest.raises(CoreError) as caught, store_lock(tmp_path, STORE_ID, 0.2):
        pass

    # Then
    release.set()
    thread.join()
    assert caught.value.code == "store.busy"


def test_a_write_waits_for_the_lock_to_be_released(store: Path) -> None:
    # Given
    reader = StoreReader(store, STORE_ID)
    head = reader.head()
    holder = hold_in_process(store, 0.5)

    # When
    commit_id = append_log(store, STORE_ID, "projects/site", "Text.", ALICE)

    # Then
    holder.wait()
    assert reader.head() == commit_id != head


def test_the_lock_is_released_after_a_failure(tmp_path: Path) -> None:
    # Given
    with pytest.raises(ValueError), store_lock(tmp_path, STORE_ID):
        raise ValueError("inside the lock")

    # When
    with store_lock(tmp_path, STORE_ID, 0.2):
        obtained = True

    # Then
    assert obtained
    assert lock_path(tmp_path, STORE_ID).is_file()
