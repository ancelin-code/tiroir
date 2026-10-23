"""The background indexer (ADR-009): a thread draining a queue of store ids.

It is fed after each commit and at start with every store of the data
directory. Indexing is derived from the commits, so a failed job is logged and
dropped: the next job for that store catches up from the recorded commit.
"""

import queue
import threading
from pathlib import Path

from loguru import logger

from tiroir.core.index import index_store


class Indexer:
    """Runs `index_store` for queued store ids on one background thread."""

    def __init__(self, data_dir: Path) -> None:
        """Prepare an indexer for the stores under `data_dir`; `start` runs it."""
        self._data_dir = data_dir
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._pending: set[str] = set()
        self._busy = False
        self._changed = threading.Condition()
        self._thread = threading.Thread(target=self._run, name="indexer", daemon=True)

    def start(self) -> None:
        """Queue every store found in the data directory, then start the thread."""
        stores = self._data_dir / "stores"
        if stores.is_dir():
            for path in sorted(stores.glob("*.git")):
                self.submit(path.name.removesuffix(".git"))
        self._thread.start()

    def submit(self, store_id: str) -> None:
        """Ask for the store to be indexed; one already waiting is not queued twice."""
        with self._changed:
            if store_id in self._pending:
                return
            self._pending.add(store_id)
        self._queue.put(store_id)

    def stop(self, timeout: float | None = 10.0) -> None:
        """Finish the queued jobs, then end the thread."""
        self._queue.put(None)
        if self._thread.is_alive():
            self._thread.join(timeout)

    def wait_idle(self, timeout: float) -> bool:
        """Wait until nothing is queued or running; false if `timeout` ran out."""
        with self._changed:
            return self._changed.wait_for(
                lambda: not self._pending and not self._busy, timeout
            )

    def _run(self) -> None:
        """Take store ids until told to stop, indexing each."""
        while (store_id := self._queue.get()) is not None:
            with self._changed:
                self._pending.discard(store_id)
                self._busy = True
            try:
                report = index_store(self._data_dir, store_id)
                logger.info(
                    "indexed store {}: {} files, {} chunks",
                    store_id,
                    report.files_indexed,
                    report.chunks,
                )
            except Exception as error:  # a job must not end the thread
                code = getattr(error, "code", type(error).__name__)
                logger.error("indexing store {} failed: {}", store_id, code)
            finally:
                with self._changed:
                    self._busy = False
                    self._changed.notify_all()
