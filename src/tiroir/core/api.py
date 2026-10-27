"""The core API (`delivery/contracts/core-api.md`): the one door into the core.

A `Core` is opened on a data directory. Members act through a `MemberContext`
and administrators through an `AdminContext`; both read the server database at
every call, so a changed grant counts at once (A4). Each call opens its own
database connection, which keeps the API thread-safe.
"""

import shutil
import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path

from tiroir.core import index, serverdb
from tiroir.core.errors import CoreError
from tiroir.core.indexer import Indexer
from tiroir.core.layout import SUMMARY_FILE, drawers_in, slug
from tiroir.core.lexical import search_lexical
from tiroir.core.presets import load_preset, with_identity
from tiroir.core.serverdb import GrantedStore, Member, StoreRow
from tiroir.core.store import (
    Author,
    StoreReader,
    append_log,
    create_store,
    repository_path,
)
from tiroir.core.types import (
    Access,
    Audience,
    Degraded,
    DrawerLine,
    DrawerRef,
    Entry,
    Filters,
    IndexReport,
    Kind,
    Log,
    ReadItem,
    ReadResult,
    ReadTarget,
    Scope,
    SearchResult,
    ServerState,
    StatusReport,
    StoreAdminInfo,
    StoreIndexReport,
    StoreInfo,
    Summary,
    Via,
    WriteOutcome,
)

_LOG_FOLDER = "log"


def open_core(data_dir: Path, *, start_workers: bool = True) -> "Core":
    """Open the data directory; `start_workers` runs the indexer in the background."""
    indexer = Indexer(data_dir) if start_workers else None
    core = Core(data_dir, indexer)
    if indexer is not None:
        indexer.start()
    return core


class Core:
    """The server database, the stores and their indexes behind one object."""

    def __init__(self, data_dir: Path, indexer: Indexer | None = None) -> None:
        """Hold `data_dir`; `open_core` is the way to get one."""
        self.data_dir = data_dir
        self._indexer = indexer
        # Creates the database and applies its migrations before any call.
        serverdb.open_server_db(data_dir).close()

    def member(
        self, member_id: str, *, session_id: str | None = None, via: Via = Via.MCP
    ) -> "MemberContext":
        """The context of a member, named by id or handle."""
        return MemberContext(self, member_id, session_id, via)

    def admin(self, member_id: str) -> "AdminContext":
        """The context of an administrator; raises `access.not-admin` otherwise."""
        with self._db() as conn:
            member = serverdb.find_active_member(conn, member_id)
        if member is None or not member.is_admin:
            raise CoreError("access.not-admin", "administrators only")
        return AdminContext(self, member)

    def close(self) -> None:
        """Stop the background indexer, if any."""
        if self._indexer is not None:
            self._indexer.stop()

    @contextmanager
    def _db(self) -> Iterator[sqlite3.Connection]:
        """A connection to the server database for one call."""
        with closing(serverdb.open_server_db(self.data_dir)) as conn:
            yield conn

    def _refresh_index(self, store_id: str) -> None:
        """Bring the store's index to its head: queued with workers, else now."""
        if self._indexer is not None:
            self._indexer.submit(store_id)
        else:
            index.index_store(self.data_dir, store_id)


def _info(granted: GrantedStore) -> StoreInfo:
    store = granted.store
    return StoreInfo(
        id=store.id,
        name=store.name,
        audience=Audience(store.audience),
        language=store.language,
        access=Access(granted.access),
        is_default=granted.is_default,
    )


class MemberContext:
    """What one member may do; their grants are read at every call."""

    def __init__(
        self, core: Core, member_id: str, session_id: str | None, via: Via
    ) -> None:
        """Bind the member; nothing is checked until a call."""
        self._core = core
        self._member_id = member_id
        self.session_id = session_id
        self.via = via

    def _grants(self) -> tuple[Member, list[GrantedStore]]:
        """The member, enabled, and their grants as of now; `auth.revoked` otherwise."""
        with self._core._db() as conn:
            member = serverdb.find_active_member(conn, self._member_id)
            if member is None:
                raise CoreError("auth.revoked", "the member is unknown or disabled")
            return member, serverdb.granted_stores(conn, member.id)

    def _granted(self, name: str | None) -> tuple[Member, GrantedStore]:
        """The grant on store `name`, or on the default store when `None`.

        An ungranted store is `store.unknown`, as one that does not exist (X1a).
        """
        member, grants = self._grants()
        if name is None:
            default = next((g for g in grants if g.is_default), None)
            if default is None:
                raise CoreError("store.no-default", "no default store")
            return member, default
        found = next((g for g in grants if g.store.name == name), None)
        if found is None:
            raise CoreError("store.unknown", f"no store {name}")
        return member, found

    def stores(self) -> list[StoreInfo]:
        """The stores the member was granted, with their access."""
        return [_info(g) for g in self._grants()[1]]

    def list_drawers(
        self, store: str | None = None, drawer_type: str | None = None
    ) -> list[DrawerLine]:
        """The drawers of one granted store, or of all of them, by type if given."""
        _, grants = self._grants()
        if store is not None:
            grants = [self._granted(store)[1]]
        lines: list[DrawerLine] = []
        for granted in grants:
            lines += self._drawers(granted.store, drawer_type)
        return lines

    def _drawers(self, store: StoreRow, drawer_type: str | None) -> list[DrawerLine]:
        """The drawer lines of a store."""
        reader = StoreReader(self._core.data_dir, store.id)
        head = reader.head()
        summaries = {
            path: (reader.read(path, head) or b"").decode("utf-8")
            for path in reader.files(head)
            if path.endswith(f"/{SUMMARY_FILE}")
        }
        drawers = drawers_in(reader.schema(head), summaries)
        return [
            DrawerLine(store.name, d.id, d.type, d.fields)
            for d in drawers
            if drawer_type in (None, d.type)
        ]

    def read(self, target: ReadTarget, scope: Scope) -> ReadResult:
        """A summary, a log or an entry of a drawer inside the scope.

        Raises `store.unknown`, `scope.denied` (the scope is checked before the
        drawer is looked up) or `drawer.unknown`.
        """
        ref = target.drawer
        _, granted = self._granted(ref.store)
        if not scope.all_drawers and ref not in scope.drawers:
            raise CoreError("scope.denied", "the drawer is outside the scope")
        reader = StoreReader(self._core.data_dir, granted.store.id)
        head = reader.head()
        summary = f"{ref.drawer}/{SUMMARY_FILE}"
        if reader.read(summary, head) is None:
            raise CoreError("drawer.unknown", f"no drawer {ref.drawer}")
        match target:
            case Summary():
                paths, kind = [summary], Kind.SUMMARY
            case Log(limit=limit, before=before):
                paths = self._entries(reader, head, ref.drawer)
                if before is not None:
                    paths = [p for p in paths if _entry_id(p) < before]
                paths, kind = paths[: max(limit, 0)], Kind.LOG
            case Entry(entry_id=entry_id):
                paths = [
                    p
                    for p in self._entries(reader, head, ref.drawer)
                    if _entry_id(p) == entry_id
                ]
                if not paths:
                    raise CoreError("entry.unknown", f"no entry {entry_id}")
                kind = Kind.LOG
        items = tuple(
            ReadItem(p, (reader.read(p, head) or b"").decode("utf-8")) for p in paths
        )
        return ReadResult(ref, kind, items)

    @staticmethod
    def _entries(reader: StoreReader, head: str, drawer: str) -> list[str]:
        """The drawer's log entry paths, newest first."""
        prefix = f"{drawer}/{_LOG_FOLDER}/"
        paths = [p for p in reader.files(head) if p.startswith(prefix)]
        return sorted(paths, key=_entry_id, reverse=True)

    def search(
        self,
        query: str,
        scope: Scope,
        filters: Filters = Filters(),  # noqa: B008 - frozen
        limit: int = 10,
    ) -> SearchResult:
        """Lexical search over the granted stores, narrowed by scope and filters.

        Vector search is not built yet, so the result reports `vectors-pending`.
        A store named in the scope or the filters that was not granted raises
        `store.unknown`.
        """
        _, grants = self._grants()
        by_name = {g.store.name: g.store.id for g in grants}
        named = {d.store for d in scope.drawers} | set(filters.stores)
        ungranted = sorted(named - by_name.keys())
        if ungranted:
            raise CoreError("store.unknown", f"no store {ungranted[0]}")
        hits = search_lexical(
            self._core.data_dir, list(by_name.values()), query, scope, filters, limit
        )
        return SearchResult(tuple(hits), not hits, (Degraded.VECTORS_PENDING,))

    def append_log(self, drawer: DrawerRef, body: str) -> WriteOutcome:
        """Add a log entry to a drawer; applied at once in a personal store.

        Raises `store.unknown`, `access.read-only` or, for a team store whose
        proposals are not built yet, `not-implemented`.
        """
        member, granted = self._granted(drawer.store)
        if Access(granted.access) is Access.READ:
            raise CoreError("access.read-only", f"{drawer.store} is read-only")
        if Audience(granted.store.audience) is not Audience.PERSONAL:
            raise CoreError("not-implemented", "proposals are not built yet")
        author = Author(member.handle, member.display_name, self.via.value)
        commit = append_log(
            self._core.data_dir, granted.store.id, drawer.drawer, body, author
        )
        self._core._refresh_index(granted.store.id)
        return WriteOutcome(True, None, commit)

    def status(self) -> StatusReport:
        """The member's stores and access, and the degraded modes in force."""
        return StatusReport(tuple(self.stores()), (Degraded.VECTORS_PENDING,))


def _entry_id(path: str) -> str:
    """A log entry's id: its file name without `.md`."""
    return path.rpartition("/")[2].removesuffix(".md")


class AdminContext:
    """What an administrator may do; never returns memory content (A3)."""

    def __init__(self, core: Core, member: Member) -> None:
        """Bind the administrator."""
        self._core = core
        self._member = member

    def _store(self, conn: sqlite3.Connection, name: str) -> StoreRow:
        store = serverdb.find_store(conn, name)
        if store is None:
            raise CoreError("store.unknown", f"no store {name}")
        return store

    def _member_of(self, conn: sqlite3.Connection, handle: str) -> Member:
        member = serverdb.find_member(conn, handle)
        if member is None:
            raise CoreError("member.unknown", f"unknown member {handle}")
        if member.disabled is not None:
            raise CoreError("member.disabled", f"member {handle} is disabled")
        return member

    def create_store(
        self,
        name: str,
        audience: Audience,
        language: str,
        owner: str | None = None,
        preset: Path | None = None,
    ) -> StoreAdminInfo:
        """Create a store from a preset directory, grant its owner and index it.

        The owner gets `write` and the store becomes their default. A personal
        store needs an owner. Raises `params.invalid`, `member.unknown`,
        `store.exists`, `schema.invalid` or `preset.required`.
        """
        if not name or name != slug(name):
            raise CoreError("params.invalid", "a store name is a lowercase slug")
        if audience is Audience.PERSONAL and owner is None:
            raise CoreError("params.invalid", "a personal store needs an owner")
        if preset is None:
            raise CoreError("preset.required", "a store is created from a preset")
        with self._core._db() as conn:
            if serverdb.find_store(conn, name) is not None:
                raise CoreError("store.exists", f"store {name} already exists")
            holder = None if owner is None else self._member_of(conn, owner)
            store_id, files = with_identity(
                load_preset(preset), name, audience.value, language
            )
            create_store(
                self._core.data_dir,
                store_id,
                files,
                Author(self._member.handle, self._member.display_name, Via.ADMIN.value),
            )
            try:
                row = serverdb.insert_store(
                    conn, store_id, name, audience.value, language
                )
                if holder is not None:
                    serverdb.set_grant(
                        conn, holder.id, store_id, Access.WRITE.value, make_default=True
                    )
            except serverdb.ServerDbError as error:
                shutil.rmtree(repository_path(self._core.data_dir, store_id))
                raise CoreError(
                    "store.exists", f"store {name} already exists"
                ) from error
        self._core._refresh_index(store_id)
        return StoreAdminInfo(
            row.id, name, audience, language, 0 if holder is None else 1
        )

    def stores(self) -> list[StoreAdminInfo]:
        """Every store with the number of members granted on it."""
        with self._core._db() as conn:
            return [
                StoreAdminInfo(
                    s.id,
                    s.name,
                    Audience(s.audience),
                    s.language,
                    len(serverdb.store_grant_holders(conn, s.id)),
                )
                for s in serverdb.list_stores(conn)
            ]

    def grant(self, handle: str, store: str, access: Access) -> None:
        """Give a member access to a store; a personal store has its owner only."""
        with self._core._db() as conn:
            row = self._store(conn, store)
            member = self._member_of(conn, handle)
            others = set(serverdb.store_grant_holders(conn, row.id)) - {member.id}
            if Audience(row.audience) is Audience.PERSONAL and others:
                raise CoreError("access.personal", f"{store} is a personal store")
            serverdb.set_grant(conn, member.id, row.id, access.value)

    def revoke(self, handle: str, store: str) -> None:
        """Remove a member's access to a store; they need not hold any."""
        with self._core._db() as conn:
            row = self._store(conn, store)
            member = serverdb.find_member(conn, handle)
            if member is None:
                raise CoreError("member.unknown", f"unknown member {handle}")
            serverdb.delete_grant(conn, member.id, row.id)

    def index(self, store: str | None = None, rebuild: bool = False) -> IndexReport:
        """Bring one store's index, or all, to its head; `rebuild` starts over."""
        with self._core._db() as conn:
            rows = (
                serverdb.list_stores(conn)
                if store is None
                else [self._store(conn, store)]
            )
        run = index.rebuild if rebuild else index.index_store
        reports: list[StoreIndexReport] = []
        for row in rows:
            done = run(self._core.data_dir, row.id)
            reports.append(
                StoreIndexReport(
                    row.name,
                    done.commit,
                    done.files_indexed,
                    done.files_removed,
                    done.chunks,
                    done.rebuilt,
                )
            )
        return IndexReport(tuple(reports))

    def state(self) -> ServerState:
        """The stores and their member counts; no memory content (A3)."""
        return ServerState(tuple(self.stores()))
