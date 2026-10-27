"""The types of the core API (`delivery/contracts/core-api.md`) and `to_json`.

Result types are frozen dataclasses and enums. `Channel`, `DrawerRef`, `Scope`,
`Filters`, `Hit` and `Kind` are defined where search uses them and exported
from here with the others.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass, fields, is_dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from tiroir.core.chunking import Kind
from tiroir.core.lexical import Channel, DrawerRef, Filters, Hit, Scope

__all__ = [
    "Access",
    "Audience",
    "Channel",
    "Degraded",
    "DrawerLine",
    "DrawerRef",
    "Entry",
    "Filters",
    "Hit",
    "IndexReport",
    "Kind",
    "Log",
    "Proposal",
    "ProposalKind",
    "ProposalStatus",
    "ReadItem",
    "ReadResult",
    "ReadTarget",
    "Scope",
    "SearchResult",
    "ServerState",
    "StatusReport",
    "StoreAdminInfo",
    "StoreIndexReport",
    "StoreInfo",
    "Summary",
    "Via",
    "WriteOutcome",
    "to_json",
]


class Audience(Enum):
    PERSONAL = "personal"
    TEAM = "team"


class Access(Enum):
    READ = "read"
    WRITE = "write"


class Via(Enum):
    MCP = "mcp"
    CLI = "cli"
    ADMIN = "admin"
    UPGRADE = "upgrade"


class Degraded(Enum):
    MODEL_LOADING = "model-loading"
    VECTORS_PENDING = "vectors-pending"
    NOT_CALIBRATED = "not-calibrated"
    EXTERNAL_UNAVAILABLE = "external-unavailable"


class ProposalKind(Enum):
    LOG_APPEND = "log-append"
    SUMMARY_UPDATE = "summary-update"
    DOC_UPDATE = "doc-update"
    DOC_CREATE = "doc-create"
    DRAWER_CREATE = "drawer-create"
    MIGRATION = "migration"
    PURGE = "purge"
    STORE_INIT = "store-init"


class ProposalStatus(Enum):
    PENDING = "pending"
    STALE = "stale"
    APPLIED = "applied"
    DISCARDED = "discarded"
    EXPIRED = "expired"


@dataclass(frozen=True)
class StoreInfo:
    """A store as the calling member sees it."""

    id: str
    name: str
    audience: Audience
    language: str
    access: Access
    is_default: bool


@dataclass(frozen=True)
class DrawerLine:
    """A drawer of a store with its metadata fields."""

    store: str
    drawer: str
    type: str
    fields: Mapping[str, Any]


@dataclass(frozen=True)
class Summary:
    """Read target: a drawer's summary."""

    drawer: DrawerRef


@dataclass(frozen=True)
class Log:
    """Read target: a drawer's log, newest first, entries before `before`."""

    drawer: DrawerRef
    limit: int = 20
    before: str | None = None


@dataclass(frozen=True)
class Entry:
    """Read target: one log entry, by its id (the file name without `.md`)."""

    drawer: DrawerRef
    entry_id: str


ReadTarget = Summary | Log | Entry


@dataclass(frozen=True)
class ReadItem:
    path: str
    text: str


@dataclass(frozen=True)
class ReadResult:
    drawer: DrawerRef
    kind: Kind
    items: tuple[ReadItem, ...]


@dataclass(frozen=True)
class SearchResult:
    hits: tuple[Hit, ...]
    abstained: bool
    degraded: tuple[Degraded, ...]


@dataclass(frozen=True)
class Proposal:
    id: str
    kind: ProposalKind
    store: StoreInfo
    paths: tuple[str, ...]
    diff: str
    status: ProposalStatus
    created: datetime
    intent: str | None


@dataclass(frozen=True)
class WriteOutcome:
    applied: bool
    proposal: Proposal | None
    commit: str | None


@dataclass(frozen=True)
class StatusReport:
    """What the member can reach and what is degraded (stores and access only)."""

    stores: tuple[StoreInfo, ...]
    degraded: tuple[Degraded, ...]


@dataclass(frozen=True)
class StoreIndexReport:
    """What indexing did to one store."""

    store: str
    commit: str
    files_indexed: int
    files_removed: int
    chunks: int
    rebuilt: bool


@dataclass(frozen=True)
class IndexReport:
    stores: tuple[StoreIndexReport, ...]


@dataclass(frozen=True)
class StoreAdminInfo:
    """A store as the administrator sees it: identity and grants, no content (A3)."""

    id: str
    name: str
    audience: Audience
    language: str
    members: int


@dataclass(frozen=True)
class ServerState:
    stores: tuple[StoreAdminInfo, ...]


def _plain(value: object) -> Any:
    """`value` as JSON-ready data: dataclasses become mappings, enums their value."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: _plain(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, Mapping):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (tuple, list, set, frozenset)):
        return [_plain(v) for v in value]
    return value


def to_json(obj: object) -> str:
    """The JSON text of a result type, as the MCP server and `--json` emit it."""
    return json.dumps(_plain(obj), ensure_ascii=False)
