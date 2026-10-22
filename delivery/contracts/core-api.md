# Contract: core API

**Status:** agreed
**Parties:** `tiroir.core` (provider); `tiroir.server` (MCP tools, account and
administration pages, Git endpoint), `tiroir.cli` (administration CLI),
`tiroir.adapters.*`, the evaluation harness (consumers).

## Purpose

The only door into the core (ADR-013). Surfaces and adapters call these
functions and never touch the database, repositories, indexes or models
themselves, so access, isolation, confirmation and history rules are enforced
in one place (ADR-004).

## Shape

Python, package `tiroir.core`; everything below is importable from
`tiroir.core`. Result types are frozen `dataclasses` (or `enum.Enum`), fully
type-annotated, and serialisable to JSON by `tiroir.core.to_json(obj)`: the
MCP server's `structuredContent` and the CLI's `--json` output are exactly that
serialisation. Every failure raises `tiroir.core.CoreError` (or a subclass)
carrying a stable `code` string (the codes in this contract and in
`schema.md` and `store-layout.md`) and a message free of memory content (Y5).

The API is synchronous and thread-safe. The server calls it from a thread pool
(ADR-009); one `Core` instance is shared by the whole process.

### Opening

```python
def open_core(data_dir: Path, *, start_workers: bool = True) -> Core: ...
```

`Core` holds the server database, the stores, the indexes and the embedding
models. `start_workers=False` is used by the administration CLI and tests.

### Calling as a member

Every member operation goes through a `MemberContext`, obtained from the
authenticated member id. The core reads the member's status and grants from
the database at each call (ADR-015), so a revoked grant fails at once (A4).

```python
class Core:
    def member(self, member_id: str, *, session_id: str | None = None,
               via: Via = Via.MCP) -> MemberContext: ...
    def admin(self, member_id: str) -> AdminContext: ...   # raises access.not-admin
```

### Shared types

```python
class Audience(Enum): PERSONAL = "personal"; TEAM = "team"
class Access(Enum): READ = "read"; WRITE = "write"
class Kind(Enum): SUMMARY = "summary"; LOG = "log"; SHARED = "shared"
class Channel(Enum): LEXICAL = "lexical"; VECTOR = "vector"; IDENTIFIER = "identifier"
class Via(Enum): MCP = "mcp"; CLI = "cli"; ADMIN = "admin"; UPGRADE = "upgrade"

@dataclass(frozen=True)
class StoreInfo:
    id: str; name: str; audience: Audience; language: str
    access: Access          # the calling member's access
    is_default: bool        # the member's default store for writes (M4)

@dataclass(frozen=True)
class DrawerRef:            # "store:drawer", e.g. "cabinet-exemple:clients/c042"
    store: str; drawer: str
    @classmethod
    def parse(cls, text: str) -> "DrawerRef": ...   # raises params.invalid

@dataclass(frozen=True)
class Scope:
    drawers: tuple[DrawerRef, ...] = ()   # empty and all_drawers False: shared spaces only (M5)
    all_drawers: bool = False             # the explicit cross-drawer request (X2)

@dataclass(frozen=True)
class Filters:
    types: tuple[str, ...] = (); stores: tuple[str, ...] = ()
    fields: Mapping[str, str] = field(default_factory=dict); kinds: tuple[Kind, ...] = ()
    since: date | None = None; until: date | None = None

@dataclass(frozen=True)
class Hit:
    store: str; drawer: str | None; path: str; kind: Kind; section: str | None
    date: date | None; author: str | None; text: str; score: float
    channels: tuple[Channel, ...]

class Degraded(Enum):
    MODEL_LOADING = "model-loading"; VECTORS_PENDING = "vectors-pending"
    NOT_CALIBRATED = "not-calibrated"; EXTERNAL_UNAVAILABLE = "external-unavailable"

@dataclass(frozen=True)
class SearchResult:
    hits: tuple[Hit, ...]; abstained: bool; degraded: tuple[Degraded, ...]

class LinkKind(Enum): EXPLICIT = "explicit"; MENTION = "mention"

@dataclass(frozen=True)
class Link:                 # never the other end's content (L4)
    kind: LinkKind; source: str; section: str | None; other: str
    other_drawer: DrawerRef | None; matched_text: str; resolved: bool

@dataclass(frozen=True)
class LinkList:
    outgoing: tuple[Link, ...]; incoming: tuple[Link, ...]

class DetectedVia(Enum): NAME = "name"; CWD = "cwd"

@dataclass(frozen=True)
class Detection: drawer: DrawerRef; matched_text: str; via: DetectedVia
@dataclass(frozen=True)
class Ambiguity: matched_text: str; candidates: tuple[DrawerRef, ...]
@dataclass(frozen=True)
class Conventions: store: str; text: str           # already capped (C5a)
@dataclass(frozen=True)
class ContextBlock:
    drawer: DrawerRef; label: str; names: tuple[str, ...]; audience: Audience
    sections: tuple[str, ...]; text: str           # already capped (C4)
@dataclass(frozen=True)
class ContextResult:
    detections: tuple[Detection, ...]; ambiguities: tuple[Ambiguity, ...]
    conventions: tuple[Conventions, ...]; blocks: tuple[ContextBlock, ...]

class ProposalKind(Enum):
    LOG_APPEND = "log-append"; SUMMARY_UPDATE = "summary-update"
    DOC_UPDATE = "doc-update"; DOC_CREATE = "doc-create"
    DRAWER_CREATE = "drawer-create"; MIGRATION = "migration"; PURGE = "purge"
    STORE_INIT = "store-init"
class ProposalStatus(Enum):
    PENDING = "pending"; STALE = "stale"; APPLIED = "applied"
    DISCARDED = "discarded"; EXPIRED = "expired"

@dataclass(frozen=True)
class Proposal:
    id: str; kind: ProposalKind; store: StoreInfo; paths: tuple[str, ...]
    diff: str; status: ProposalStatus; created: datetime; intent: str | None

@dataclass(frozen=True)
class WriteOutcome:
    applied: bool; proposal: Proposal | None; commit: str | None
```

`ReadTarget` is one of `Summary(drawer)`, `Log(drawer, limit=20, before=None)`,
`Entry(drawer, entry_id)`, `Shared(store, path)`. `DrawerLine`, `ReadResult`,
`FieldValue`, `SchemaSource`, `Renames`, `PurgeTarget`, `StatusReport`,
`DoctorReport`, `IndexReport`, `SkillArchive`, `EvalReport`, `MemberInfo`,
`StoreAdminInfo`, `MirrorInfo` and `ServerState` are defined by the core with
the same conventions; the surfaces only serialise or render them.

### Member operations

```python
class MemberContext:
    # Reading: never writes to a store; only granted stores are visible (X1a)
    def stores(self) -> list[StoreInfo]: ...
    def list_drawers(self, store: str | None = None, drawer_type: str | None = None) -> list[DrawerLine]: ...
    def read(self, target: ReadTarget, scope: Scope) -> ReadResult: ...
    def links(self, target: ReadTarget, scope: Scope) -> LinkList: ...            # L4, ADR-014
    def search(self, query: str, scope: Scope, filters: Filters = Filters(), limit: int = 10) -> SearchResult: ...

    # Context: the hook path and the MCP context tool use only this
    def context(self, text: str, cwd: str | None, deadline: float) -> ContextResult: ...  # never raises

    # Writing: applied False means a proposal awaits confirmation
    def append_log(self, drawer: DrawerRef, body: str) -> WriteOutcome: ...
    def propose_summary(self, drawer: DrawerRef, new_text: str, intent: str) -> WriteOutcome: ...
    def create_drawer(self, store: str | None, drawer_type: str, fields: Mapping[str, FieldValue]) -> WriteOutcome: ...
    def write_shared(self, store: str | None, path: str, new_text: str, intent: str) -> WriteOutcome: ...

    # Proposals: only the member's own (ADR-012)
    def proposals(self, store: str | None = None) -> list[Proposal]: ...
    def confirm(self, proposal_id: str) -> WriteOutcome: ...
    def discard(self, proposal_id: str) -> None: ...

    # Store work by a member holding write access; each returns a proposal
    def init_store(self, store: str, schema: SchemaSource) -> Proposal: ...       # store created by an administrator (I2)
    def plan_migration(self, store: str, new_schema: str, renames: Renames) -> Proposal: ...   # diff = dry run (I4)
    def plan_purge(self, target: PurgeTarget) -> Proposal: ...                    # diff = dry run (E1)

    def status(self) -> StatusReport: ...      # stores, access, pending and stale proposals, skill freshness, degraded modes
    def doctor(self, store: str | None = None) -> DoctorReport: ...
    def memory_skill(self) -> SkillArchive: ...                                    # ADR-013
    def evaluate(self, store: str, queries: Path | None = None) -> EvalReport: ...  # V1, V4
```

### Administration operations

```python
class AdminContext:
    def members(self) -> list[MemberInfo]: ...
    def create_member(self, handle: str, display_name: str, initial_password: str, admin: bool = False) -> MemberInfo: ...
    def disable_member(self, handle: str) -> None: ...                 # revokes grants, tokens, sessions (A4)
    def create_store(self, name: str, audience: Audience, language: str, owner: str | None = None) -> StoreAdminInfo: ...
    def grant(self, handle: str, store: str, access: Access) -> None: ...
    def revoke(self, handle: str, store: str) -> None: ...
    def set_embedding(self, store: str, model: EmbeddingChoice) -> None: ...      # R4; starts a re-index
    def add_mirror(self, store: str, url: str) -> MirrorInfo: ...                 # Y6; SSH: returns the public key
    def remove_mirror(self, store: str, mirror_id: str) -> None: ...
    def calibrate(self, store: str, queries: Path | None = None) -> EvalReport: ...  # V4
    def index(self, store: str | None = None, rebuild: bool = False) -> IndexReport: ...
    def state(self) -> ServerState: ...                                           # A3: no memory content
    def backup(self, target: Path) -> None: ...                                   # A6, ADR-016
    def restore(self, source: Path) -> None: ...
```

### Rules every implementation keeps

- Every `MemberContext` call resolves the member's grants first; a store the
  member was not granted behaves exactly like a store that does not exist:
  `store.unknown`, never `scope.denied` (X1a).
- `search`, `read`, `links` and `context` filter by scope **before** ranking or
  reading (X1); a `read` outside the scope returns `scope.denied`.
- `context` never embeds, never runs past `deadline` seconds, and on any
  internal error returns an empty `ContextResult` (C6). `conventions` holds a
  store's conventions only the first time that store is used in the member's
  `session_id` (C5a).
- A write targets exactly one store; `store=None` means the member's default
  store (M4), and `store.no-default` when they have none.
- A write to a store with `read` access raises `access.read-only` before any
  proposal is made (W6).
- `append_log` to a `personal` store applies immediately; every other write,
  and any write to a `team` store, returns a pending proposal (W2, W5).
- Writes, confirmations, migrations and purges hold the store's write lock
  (ADR-009, ADR-010).
- `AdminContext` never returns memory content (A3), and its changes to members
  and grants take effect at the next member call (A4).

## Example

```python
core = open_core(Path("/data"))
alice = core.member("m-alice", session_id="s1")
res = alice.context("Prépare la relance TVA pour Boulangerie Dupont", None, deadline=1.2)
# str(res.detections[0].drawer) == "cabinet-exemple:clients/c042"
# res.blocks[0].sections == ("Identité", "Points d'attention", "Échéances")
out = alice.append_log(DrawerRef.parse("cabinet-exemple:clients/c042"), "Relance TVA préparée.")
# team store: out.applied is False, out.proposal.status is ProposalStatus.PENDING
done = alice.confirm(out.proposal.id)    # after the user said yes
assert done.applied
```

## Error cases

| Condition | Code |
|---|---|
| Unknown store, or a store the member was not granted | `store.unknown` |
| Unknown drawer | `drawer.unknown` |
| Read or search outside the scope | `scope.denied` |
| Write to a store with read access | `access.read-only` (W6) |
| Administration call by a non-administrator | `access.not-admin` |
| Member disabled or token revoked | `auth.revoked` |
| Schema invalid (S6) | `schema.invalid` (no write happens) |
| Metadata fails validation on create | `metadata.invalid` |
| Write holding an explicit link that resolves to nothing | `link.unresolved` (L2) |
| Confirming a proposal whose base changed | not an error: returns a new pending proposal, or the old one marked `stale` (Y4b) |
| Proposal expired, unknown or another member's | `proposal.unknown` |
| Write into a purged drawer, or of purged content | `drawer.purged` (Y4e, E2) |
| No default store and no store named | `store.no-default` |
| Store lock not obtained within 10 s (migration or purge running) | `store.busy` |
| Commits on `main` not made by tiroir | `store.foreign-change`; the store is read-only until resolved (ADR-010) |

## Changing this contract

Lanes are building against this. A change needs agreement from every party
listed above, and the lanes must be told; a silent change produces work that
cannot be integrated.
