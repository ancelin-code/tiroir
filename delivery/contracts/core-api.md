# Contract: core API

**Status:** draft
**Parties:** `tiroir.core` (provider); `tiroir.mcp`, `tiroir.cli`,
`tiroir.adapters.claude_code`, the evaluation harness (consumers).

## Purpose

The only door into the core (ADR-013). Surfaces and adapters call these
functions and never touch files, the index or Git themselves, so isolation,
confirmation and sync rules are enforced in one place.

## Shape

Python 3.12. All public names are importable from `tiroir.core`. Results are
frozen dataclasses; every error is a `TiroirError` subclass carrying a stable
`code` string (the codes in this contract and in `schema.md` and
`store-layout.md`) and a message free of memory content (Y5).

### Opening

```python
def open_workspace(config_path: Path | None = None) -> Workspace
```

A `Workspace` is the machine configuration plus every store in use. It is
cheap to open and safe to use from one thread; processes do not share it.

### Shared types

| Type | Fields |
|---|---|
| `StoreInfo` | `id: str`, `name: str`, `audience: Literal["personal","team"]`, `language: str`, `path: Path`, `remote: str \| None`, `is_default: bool` |
| `DrawerRef` | `store: str` (name), `drawer: str` (drawer id). `str()` gives `store:drawer`. |
| `Scope` | `drawers: tuple[DrawerRef, ...]`, `all_drawers: bool = False`. Empty `drawers` and `all_drawers=False` means shared spaces only (M5); `all_drawers=True` is the explicit cross-drawer search (X2). |
| `Filters` | `types`, `stores: tuple[str, ...] = ()`, `fields: dict[str, str] = {}`, `kinds: tuple[Literal["summary","log","shared"], ...] = ()`, `since: date \| None`, `until: date \| None` |
| `Hit` | `store`, `drawer: str \| None` (None for shared), `path`, `kind`, `section: str \| None`, `date: date \| None`, `author: str \| None`, `text: str`, `score: float`, `channels: frozenset[Literal["lexical","vector","identifier"]]` |
| `SearchResult` | `hits: tuple[Hit, ...]`, `abstained: bool`, `degraded: tuple[str, ...]` (for example `"vectors-pending"`, `"model-loading"`) |
| `Detection` | `drawer: DrawerRef`, `matched_text: str`, `via: Literal["name","cwd"]` |
| `Ambiguity` | `matched_text: str`, `candidates: tuple[DrawerRef, ...]` |
| `ContextResult` | `detections`, `ambiguities`, `conventions: str \| None`, `blocks: tuple[ContextBlock, ...]` |
| `ContextBlock` | `drawer: DrawerRef`, `store_audience`, `sections: tuple[str, ...]`, `text: str` (already capped, C4) |
| `Proposal` | `id`, `kind`, `store: StoreInfo`, `paths: tuple[str, ...]`, `diff: str`, `status: Literal["pending","stale","applied","discarded","expired"]`, `created: datetime`, `intent: str \| None` (for stale proposals to redo, Y4b) |
| `WriteOutcome` | `applied: bool`, `proposal: Proposal \| None`, `commit: str \| None`, `pushed: bool` |
| `SyncReport` | per store: `fetched`, `pushed`, `replayed`, `queued`, `stale_proposals`, `refused` (Y4e), `outside_edits`, `stopped: str \| None` |

### Operations

```python
# Reading (never writes to a store)
Workspace.stores() -> tuple[StoreInfo, ...]
Workspace.list_drawers(store: str | None = None, type: str | None = None) -> tuple[DrawerSummaryLine, ...]
Workspace.read(ref: DrawerRef | str, part: Literal["summary","log","entry","shared"] = "summary",
               *, limit: int = 20, before: datetime | None = None, scope: Scope) -> ReadResult
Workspace.search(query: str, scope: Scope, filters: Filters = Filters(), limit: int = 10) -> SearchResult

# Context (the adapter and the MCP context tool use only this)
Workspace.context(text: str, *, cwd: Path | None = None, session_id: str | None = None,
                  deadline_s: float = 1.5) -> ContextResult

# Writing (each returns WriteOutcome; applied=False means a proposal awaits confirmation)
Workspace.append_log(drawer: DrawerRef, body: str) -> WriteOutcome
Workspace.propose_summary(drawer: DrawerRef, new_text: str, intent: str) -> WriteOutcome
Workspace.create_drawer(store: str | None, type: str, fields: dict[str, Any]) -> WriteOutcome
Workspace.write_shared(store: str | None, path: str, new_text: str, intent: str) -> WriteOutcome

# Proposals
Workspace.proposals(store: str | None = None) -> tuple[Proposal, ...]
Workspace.confirm(proposal_id: str) -> WriteOutcome
Workspace.discard(proposal_id: str) -> None

# Administration (each returns a proposal; nothing changes before confirm)
Workspace.init_store(path: Path, schema: str | Preset, *, name: str, audience: str, remote: str | None) -> Proposal
Workspace.connect_store(remote: str, path: Path | None = None) -> ConnectStep   # public key + host instructions, then .finish()
Workspace.plan_migration(store: str, new_schema: str, renames: Renames) -> Proposal   # diff = dry run (I4)
Workspace.plan_purge(target: DrawerRef | str) -> Proposal                                # diff = dry run (E1)
Workspace.sync(store: str | None = None) -> SyncReport
Workspace.doctor(store: str | None = None) -> DoctorReport
Workspace.index(store: str | None = None, rebuild: bool = False) -> IndexReport
Workspace.memory_skill() -> SkillFiles      # generated memory skill (ADR-013)
Workspace.evaluate(store: str, queries: Path, *, calibrate: bool = False) -> EvalReport
```

### Rules every implementation keeps

- `search`, `read` and `context` filter by scope **before** ranking or reading
  (X1); a `read` outside the scope raises `scope.denied`.
- `context` never loads the embedding model, never syncs and never blocks past
  `deadline_s`; on any internal error it returns an empty `ContextResult`
  (C6). `conventions` is set only the first time a `session_id` (or, without
  one, the process) gets a non-empty result (C5a).
- A write targets exactly one store; `store=None` means the default store (M4).
- `append_log` to a `personal` store applies immediately; every other write,
  and any write to a `team` store, returns a pending proposal (W2, W5).
- Writes sync before and after (Y3, Y2) and hold the store lock (ADR-010).

## Example

```python
ws = open_workspace()
res = ws.context("Prépare la relance TVA pour Boulangerie Dupont", session_id="s1")
# res.detections == (Detection(DrawerRef("cabinet-exemple", "clients/c042"), "Boulangerie Dupont", "name"),)
# res.blocks[0].sections == ("Identité", "Points d'attention", "Échéances")
out = ws.append_log(DrawerRef("cabinet-exemple", "clients/c042"), "Relance TVA préparée.")
# team store: out.applied is False, out.proposal.status == "pending"
ws.confirm(out.proposal.id).applied  # True after the user said yes
```

## Error cases

| Condition | Code |
|---|---|
| Unknown store name or drawer id | `store.unknown`, `drawer.unknown` |
| Read or search outside the scope | `scope.denied` |
| Schema invalid (S6) | `schema.invalid` (no write happens) |
| Metadata fails validation on create | `metadata.invalid` |
| Confirming a proposal whose base changed | not an error: returns a new pending proposal, or the old one marked `stale` (Y4b) |
| Proposal expired or unknown | `proposal.unknown` |
| Write into a drawer purged elsewhere | `drawer.purged` (Y4e) |
| Store lock not obtained within 10 s | `store.busy` |
| Remote unreachable | not an error: `WriteOutcome.pushed is False`, change queued (Y4c) |
| History rewritten outside tiroir | `sync.foreign-rewrite` (ADR-010) |

## Changing this contract

Lanes are building against this. A change needs agreement from every party
listed above, and the lanes must be told; a silent change produces work that
cannot be integrated.
