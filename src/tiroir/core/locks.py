"""The per-store write lock (ADR-009): an `fcntl` lock on `<data>/locks/<store-id>`.

The lock is taken on a file of its own, opened afresh at each acquisition, so
it excludes threads of one process as well as other processes, such as the
administration CLI running beside the server. Reads never take it.
"""

import fcntl
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from tiroir.core.errors import CoreError

BUSY = "store.busy"
LOCK_TIMEOUT = 10.0
_POLL_INTERVAL = 0.01


def lock_path(data_dir: Path, store_id: str) -> Path:
    """The lock file of a store."""
    return data_dir / "locks" / store_id


@contextmanager
def store_lock(
    data_dir: Path, store_id: str, timeout: float = LOCK_TIMEOUT
) -> Iterator[None]:
    """Hold the store's write lock for the `with` block.

    Raises `store.busy` when the lock is not obtained within `timeout` seconds.
    """
    path = lock_path(data_dir, store_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as file:
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise CoreError(
                        BUSY,
                        f"store {store_id} is busy with another write; retry shortly",
                    ) from None
                time.sleep(_POLL_INTERVAL)
        try:
            yield
        finally:
            fcntl.flock(file, fcntl.LOCK_UN)
