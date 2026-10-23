"""Stores as bare Git repositories, written by tiroir alone (ADR-010).

A store lives at `<data>/stores/<store-id>.git`, with one branch `main` and a
linear history. Nothing is checked out: `StoreReader` reads files from
commits, and `StoreWriter` makes one operation's commit from the head under
the store's write lock, then moves `main` with a compare-and-swap on the old
head. File shapes and commit messages come from `tiroir.core.layout`.
"""

import re
import shutil
import tempfile
from collections.abc import Iterable, Mapping
from contextlib import ExitStack
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Self

import pygit2
from pygit2.enums import FileMode

from tiroir.core.errors import CoreError, Violation
from tiroir.core.layout import (
    MEMORY_FILE,
    SCHEMA_FILE,
    SUMMARY_FILE,
    commit_message,
    drawer_path,
    drawers_in,
    log_entry_path,
    new_suffix,
    render_log_entry,
    render_memory,
    render_summary,
)
from tiroir.core.locks import LOCK_TIMEOUT, store_lock
from tiroir.core.schema import INVALID, Schema, load_schema, validate_metadata

BRANCH = "refs/heads/main"
_STORE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")
_SUFFIX_ATTEMPTS = 8


@dataclass(frozen=True)
class Author:
    """Who makes a change and through which surface (`Tiroir-Via`)."""

    handle: str
    display_name: str
    via: str

    def signature(self) -> pygit2.Signature:
        """The commit author and committer: `<display name> <handle@tiroir.invalid>`."""
        return pygit2.Signature(self.display_name, f"{self.handle}@tiroir.invalid")


def repository_path(data_dir: Path, store_id: str) -> Path:
    """`<data>/stores/<store-id>.git`; raises `store.unknown` for a malformed id."""
    if not _STORE_ID.fullmatch(store_id):
        raise CoreError("store.unknown", "malformed store id")
    return data_dir / "stores" / f"{store_id}.git"


def _is_store_path(path: str) -> bool:
    """Whether `path` is a plain relative path inside the store."""
    return not any(p in ("", ".", "..", ".git") for p in path.split("/"))


def _check_paths(paths: Iterable[str]) -> None:
    """Refuse file paths that are not plain relative paths inside the store."""
    for path in paths:
        if not _is_store_path(path):
            raise ValueError(f"not a store file path: {path!r}")


def _parse_schema(text: bytes | None) -> Schema:
    """The schema from `tiroir.yaml`'s bytes; any failure is `schema.invalid` (S6)."""
    if text is None:
        raise CoreError(INVALID, f"{SCHEMA_FILE} is missing")
    try:
        return load_schema(text.decode("utf-8"))
    except UnicodeDecodeError as error:
        raise CoreError(INVALID, f"{SCHEMA_FILE} is not UTF-8") from error
    except CoreError as error:
        raise CoreError(
            INVALID, f"{SCHEMA_FILE} does not validate", error.violations
        ) from error


def _build_tree(
    repo: pygit2.Repository, base: pygit2.Tree | None, changes: Mapping[str, bytes]
) -> pygit2.Oid:
    """Write the tree `base` with `changes` (path to content) applied."""
    builder = repo.TreeBuilder(base) if base is not None else repo.TreeBuilder()
    nested: dict[str, dict[str, bytes]] = {}
    for path, data in changes.items():
        head, sep, rest = path.partition("/")
        if sep:
            nested.setdefault(head, {})[rest] = data
        else:
            builder.insert(head, repo.create_blob(data), FileMode.BLOB)
    for name, sub_changes in nested.items():
        child = base[name] if base is not None and name in base else None
        subtree = child if isinstance(child, pygit2.Tree) else None
        builder.insert(name, _build_tree(repo, subtree, sub_changes), FileMode.TREE)
    return builder.write()


class StoreReader:
    """Reads a store's commits and files; never takes the lock, never writes."""

    def __init__(self, data_dir: Path, store_id: str) -> None:
        """Open the store's repository; raises `store.unknown` when there is none."""
        self.store_id = store_id
        self.path = repository_path(data_dir, store_id)
        if not self.path.is_dir():
            raise CoreError("store.unknown", f"no store {store_id}")
        self.repo = pygit2.Repository(str(self.path))

    def head(self) -> str:
        """The commit id `main` points to."""
        return str(self.repo.references[BRANCH].target)

    def _tree(self, commit: str | None) -> pygit2.Tree:
        """The tree of `commit`, the head when `None`."""
        try:
            found = self.repo.revparse_single(commit or BRANCH)
        except pygit2.GitError:
            found = None
        if not isinstance(found, pygit2.Commit):
            raise CoreError("store.unknown-commit", "not a commit of this store")
        return found.tree

    def read(self, path: str, commit: str | None = None) -> bytes | None:
        """A file's content at `commit` (the head when `None`); `None` if absent."""
        tree = self._tree(commit)
        if path not in tree:
            return None
        found = tree[path]
        return found.data if isinstance(found, pygit2.Blob) else None

    def files(self, commit: str | None = None) -> list[str]:
        """Every file path at `commit` (the head when `None`), sorted."""
        paths: list[str] = []

        def walk(tree: pygit2.Tree, prefix: str) -> None:
            """Collect the blob paths under `tree`."""
            for entry in tree:
                if isinstance(entry, pygit2.Tree):
                    walk(entry, f"{prefix}{entry.name}/")
                elif isinstance(entry, pygit2.Blob):
                    paths.append(f"{prefix}{entry.name}")

        walk(self._tree(commit), "")
        return sorted(paths)

    def changed_paths(self, old: str | None, new: str) -> list[str]:
        """The file paths added, removed or modified from `old` to `new`, sorted.

        With `old` set to `None`, every file of `new` counts as added.
        """
        if old is None:
            return self.files(new)
        diff = self._tree(old).diff_to_tree(self._tree(new))
        changed = {d.old_file.path for d in diff.deltas}
        changed |= {d.new_file.path for d in diff.deltas}
        return sorted(changed)

    def schema(self, commit: str | None = None) -> Schema:
        """The store's validated schema; raises `schema.invalid` when it does not."""
        return _parse_schema(self.read(SCHEMA_FILE, commit))


class StoreWriter:
    """One write operation: lock, read the head, commit once, move `main`.

    Used as a context manager. Entering opens the store, takes its lock and
    refuses a store whose schema does not validate (`schema.invalid`), so
    nothing is written to it. `commit` writes the operation's one commit.
    """

    def __init__(
        self, data_dir: Path, store_id: str, lock_timeout: float = LOCK_TIMEOUT
    ) -> None:
        """Prepare a write to the store; nothing happens until entering."""
        self._data_dir = data_dir
        self._store_id = store_id
        self._lock_timeout = lock_timeout
        self._stack = ExitStack()
        self._committed = False

    def __enter__(self) -> Self:
        reader = StoreReader(self._data_dir, self._store_id)
        with ExitStack() as stack:
            stack.enter_context(
                store_lock(self._data_dir, self._store_id, self._lock_timeout)
            )
            self.reader = reader
            self._ref = reader.repo.references[BRANCH]
            self.base = str(self._ref.target)
            self.schema = reader.schema(self.base)
            self._stack = stack.pop_all()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._stack.close()

    def read(self, path: str) -> bytes | None:
        """A file's content at the base head; `None` if absent."""
        return self.reader.read(path, self.base)

    def commit(
        self,
        op: str,
        author: Author,
        changes: Mapping[str, bytes],
        drawer: str | None = None,
    ) -> str:
        """Write the operation's commit on the base head and move `main` to it.

        Raises `store.foreign-change` when `main` moved since the base was read,
        which only a writer bypassing the lock can do.
        """
        if self._committed:
            raise RuntimeError("a StoreWriter makes one commit")
        _check_paths(changes)
        repo = self.reader.repo
        parent = repo.get(self.base)
        assert isinstance(parent, pygit2.Commit)
        tree = _build_tree(repo, parent.tree, changes)
        signature = author.signature()
        message = commit_message(op, author.handle, author.via, drawer)
        commit = repo.create_commit(
            None, signature, signature, message, tree, [parent.id]
        )
        try:
            self._ref.set_target(commit, message.partition("\n")[0])
        except pygit2.GitError as error:
            raise CoreError(
                "store.foreign-change", "main moved outside the store lock"
            ) from error
        self._committed = True
        return str(commit)


def create_drawer_files(
    schema: Schema,
    type_name: str,
    fields: Mapping[str, object],
    template: str,
) -> dict[str, bytes]:
    """The files of a new drawer: its `summary.md` from the type's template.

    The drawer's folder comes from the type's path pattern. Raises
    `metadata.invalid` when `fields` do not satisfy the drawer type.
    """
    drawer_type = schema.drawer_types[type_name]
    violations = validate_metadata(drawer_type, fields)
    if violations:
        raise CoreError(
            violations[0].code, "invalid drawer metadata", tuple(violations)
        )
    text = render_summary(type_name, drawer_type, fields, template)
    folder = drawer_path(drawer_type, fields)
    return {f"{folder}/{SUMMARY_FILE}": text.encode("utf-8")}


def _memory_file(schema: Schema, files: Mapping[str, bytes]) -> bytes:
    """`MEMORY.md` generated from the drawers among `files`."""
    summaries = {
        path: data.decode("utf-8")
        for path, data in files.items()
        if path.endswith(f"/{SUMMARY_FILE}")
    }
    return render_memory(schema, drawers_in(schema, summaries)).encode("utf-8")


def create_store(
    data_dir: Path,
    store_id: str,
    files: Mapping[str, bytes],
    author: Author,
    lock_timeout: float = LOCK_TIMEOUT,
) -> str:
    """Create the store's bare repository with its `store-init` commit.

    `files` (path to content, such as a preset) must hold a valid
    `tiroir.yaml` whose `store.id` is `store_id`; `MEMORY.md` is generated from
    the drawers, replacing any given. Returns the commit id. Raises
    `schema.invalid`, `metadata.invalid`, `store.exists` or `store.busy`, and
    then leaves nothing behind.
    """
    path = repository_path(data_dir, store_id)
    schema = _parse_schema(files.get(SCHEMA_FILE))
    if schema.store.id != store_id:
        raise CoreError(
            INVALID,
            "store.id does not match the store being created",
            (Violation(INVALID, "store.id", "expected the id of the new store"),),
        )
    tree_files = {**files, MEMORY_FILE: _memory_file(schema, files)}
    _check_paths(tree_files)
    path.parent.mkdir(parents=True, exist_ok=True)
    with store_lock(data_dir, store_id, lock_timeout):
        if path.exists():
            raise CoreError("store.exists", f"store {store_id} already exists")
        # Built aside, then renamed: a failure leaves no half-made store.
        staging = Path(tempfile.mkdtemp(prefix=f".{store_id}-", dir=path.parent))
        try:
            repo = pygit2.init_repository(str(staging), bare=True, initial_head="main")
            tree = _build_tree(repo, None, tree_files)
            signature = author.signature()
            message = commit_message("store-init", author.handle, author.via)
            commit = repo.create_commit(BRANCH, signature, signature, message, tree, [])
            staging.rename(path)
        except BaseException:
            shutil.rmtree(staging, ignore_errors=True)
            raise
    return str(commit)


def append_log(
    data_dir: Path,
    store_id: str,
    drawer_id: str,
    body: str,
    author: Author,
    lock_timeout: float = LOCK_TIMEOUT,
) -> str:
    """Add one log entry to a drawer in one `log-append` commit; returns its id.

    Raises `log.invalid` for an empty body, `drawer.unknown`, `schema.invalid`
    or `store.busy`; nothing is written then.
    """
    if not body.strip():
        raise CoreError("log.invalid", "a log entry needs a body")
    if not _is_store_path(drawer_id):
        raise CoreError("drawer.unknown", "malformed drawer id")
    with StoreWriter(data_dir, store_id, lock_timeout) as writer:
        if writer.read(f"{drawer_id}/{SUMMARY_FILE}") is None:
            raise CoreError("drawer.unknown", f"no drawer {drawer_id}")
        when = datetime.now(UTC).replace(microsecond=0)
        for _ in range(_SUFFIX_ATTEMPTS):
            entry = log_entry_path(drawer_id, when, author.handle, new_suffix())
            if writer.read(entry) is None:
                break
        else:
            raise CoreError("log.modified", "no free log entry name")
        text = render_log_entry(when, author.handle, body)
        return writer.commit(
            "log-append", author, {entry: text.encode("utf-8")}, drawer=drawer_id
        )
