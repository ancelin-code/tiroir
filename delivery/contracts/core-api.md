# Contract: core API

**Status:** draft
**Parties:** `tiroir-core` (provider); `tiroir-mcp`, `tiroir-cli`,
`tiroir-adapter-claude-code`, the evaluation harness (consumers).

## Purpose

The only door into the core (ADR-013). Surfaces and adapters call these
functions and never touch files, the index or Git themselves, so isolation,
confirmation and sync rules are enforced in one place.

## Shape

Rust, crate `tiroir-core`; everything below is public at the crate root.
Result types are plain structs and enums deriving `Debug`, `Clone` and
`serde::Serialize` (the MCP server and `--json` output serialise them as is).
Every fallible function returns `Result<T, tiroir_core::Error>`. `Error`
carries a stable `code()` string (the codes in this contract and in
`schema.md` and `store-layout.md`) and a message free of memory content (Y5).

The API is synchronous. Callers on an async runtime (`tiroir-mcp` on `tokio`)
run it on a blocking thread. A `Workspace` is `Send` but not `Sync`: one per
thread, opened cheaply.

### Opening

```rust
pub fn open_workspace(config_path: Option<&Path>) -> Result<Workspace, Error>;
```

A `Workspace` is the machine configuration plus every store in use.

### Shared types

```rust
pub enum Audience { Personal, Team }
pub enum Kind { Summary, Log, Shared }
pub enum Channel { Lexical, Vector, Identifier }

pub struct StoreInfo { pub id: String, pub name: String, pub audience: Audience,
                       pub language: String, pub path: PathBuf,
                       pub remote: Option<String>, pub is_default: bool }

/// `store:drawer`, e.g. `cabinet-exemple:clients/c042`. Parsed with `FromStr`.
pub struct DrawerRef { pub store: String, pub drawer: String }

/// Empty `drawers` and `all_drawers == false`: shared spaces only (M5).
/// `all_drawers == true`: the explicit cross-drawer search (X2).
pub struct Scope { pub drawers: Vec<DrawerRef>, pub all_drawers: bool }

#[derive(Default)]
pub struct Filters { pub types: Vec<String>, pub stores: Vec<String>,
                     pub fields: BTreeMap<String, String>, pub kinds: Vec<Kind>,
                     pub since: Option<NaiveDate>, pub until: Option<NaiveDate> }

pub struct Hit { pub store: String, pub drawer: Option<String>, pub path: String,
                 pub kind: Kind, pub section: Option<String>, pub date: Option<NaiveDate>,
                 pub author: Option<String>, pub text: String, pub score: f32,
                 pub channels: Vec<Channel> }

pub struct SearchResult { pub hits: Vec<Hit>, pub abstained: bool,
                          pub degraded: Vec<Degraded> }   // VectorsPending, ModelLoading

pub enum LinkKind { Explicit, Mention }
/// `other` is the file or drawer at the other end; never its content (L4).
pub struct Link { pub kind: LinkKind, pub source: String, pub section: Option<String>,
                  pub other: String, pub other_drawer: Option<DrawerRef>,
                  pub matched_text: String, pub resolved: bool }
pub struct LinkList { pub outgoing: Vec<Link>, pub incoming: Vec<Link> }

pub enum DetectedVia { Name, Cwd }
pub struct Detection { pub drawer: DrawerRef, pub matched_text: String, pub via: DetectedVia }
pub struct Ambiguity { pub matched_text: String, pub candidates: Vec<DrawerRef> }

pub struct ContextBlock { pub drawer: DrawerRef, pub label: String, pub names: Vec<String>,
                          pub audience: Audience, pub sections: Vec<String>,
                          pub text: String }       // already capped (C4)
pub struct ContextResult { pub detections: Vec<Detection>, pub ambiguities: Vec<Ambiguity>,
                           pub conventions: Option<Conventions>, pub blocks: Vec<ContextBlock> }

pub enum ProposalKind { LogAppend, SummaryUpdate, DocUpdate, DocCreate, DrawerCreate,
                        OutsideEdit, Migration, Purge, StoreInit }
pub enum ProposalStatus { Pending, Stale, Applied, Discarded, Expired }
pub struct Proposal { pub id: String, pub kind: ProposalKind, pub store: StoreInfo,
                      pub paths: Vec<String>, pub diff: String, pub status: ProposalStatus,
                      pub created: DateTime<Utc>,
                      pub intent: Option<String> }  // for stale proposals to redo (Y4b)

pub struct WriteOutcome { pub applied: bool, pub proposal: Option<Proposal>,
                          pub commit: Option<String>, pub pushed: bool }

pub struct SyncReport { pub stores: Vec<StoreSync> }
pub struct StoreSync { pub store: String, pub fetched: bool, pub pushed: usize,
                       pub replayed: usize, pub queued: usize, pub stale_proposals: usize,
                       pub refused: usize,            // Y4e
                       pub outside_edits: usize, pub stopped: Option<String> }
```

`DrawerLine`, `ReadResult`, `Conventions`, `ConnectStep`, `Renames`,
`DoctorReport`, `IndexReport`, `SkillFiles` and `EvalReport` are defined by the
core with the same conventions; the surfaces only serialise or print them.

### Operations

```rust
impl Workspace {
    // Reading: never writes to a store
    pub fn stores(&self) -> Vec<StoreInfo>;
    pub fn list_drawers(&self, store: Option<&str>, drawer_type: Option<&str>) -> Result<Vec<DrawerLine>, Error>;
    pub fn read(&self, target: &ReadTarget, scope: &Scope) -> Result<ReadResult, Error>;
        // ReadTarget: Summary(DrawerRef) | Log { drawer, limit, before } | Entry(DrawerRef, String) | Shared { store, path }
    pub fn links(&self, target: &ReadTarget, scope: &Scope) -> Result<LinkList, Error>;   // L4, ADR-014
    pub fn search(&self, query: &str, scope: &Scope, filters: &Filters, limit: usize) -> Result<SearchResult, Error>;

    // Context: the hook adapter and the MCP context tool use only this
    pub fn context(&self, text: &str, cwd: Option<&Path>, session_id: Option<&str>,
                   deadline: Duration) -> ContextResult;           // infallible, see rules

    // Writing: applied == false means a proposal awaits confirmation
    pub fn append_log(&mut self, drawer: &DrawerRef, body: &str) -> Result<WriteOutcome, Error>;
    pub fn propose_summary(&mut self, drawer: &DrawerRef, new_text: &str, intent: &str) -> Result<WriteOutcome, Error>;
    pub fn create_drawer(&mut self, store: Option<&str>, drawer_type: &str,
                         fields: &BTreeMap<String, FieldValue>) -> Result<WriteOutcome, Error>;
    pub fn write_shared(&mut self, store: Option<&str>, path: &str, new_text: &str, intent: &str) -> Result<WriteOutcome, Error>;

    // Proposals
    pub fn proposals(&self, store: Option<&str>) -> Result<Vec<Proposal>, Error>;
    pub fn confirm(&mut self, proposal_id: &str) -> Result<WriteOutcome, Error>;
    pub fn discard(&mut self, proposal_id: &str) -> Result<(), Error>;

    // Administration: each returns a proposal; nothing changes before confirm
    pub fn init_store(&mut self, path: &Path, schema: SchemaSource, name: &str,
                      audience: Audience, remote: Option<&str>) -> Result<Proposal, Error>;
    pub fn connect_store(&mut self, remote: &str, path: Option<&Path>) -> Result<ConnectStep, Error>;
        // ConnectStep::Ssh { public_key, host_page } | Https { token_page, permissions }; then .finish(credential)
    pub fn plan_migration(&mut self, store: &str, new_schema: &str, renames: &Renames) -> Result<Proposal, Error>; // diff = dry run (I4)
    pub fn plan_purge(&mut self, target: &PurgeTarget) -> Result<Proposal, Error>;                               // diff = dry run (E1)
    pub fn sync(&mut self, store: Option<&str>) -> Result<SyncReport, Error>;
    pub fn doctor(&self, store: Option<&str>) -> Result<DoctorReport, Error>;
    pub fn index(&mut self, store: Option<&str>, rebuild: bool) -> Result<IndexReport, Error>;
    pub fn memory_skill(&self) -> Result<SkillFiles, Error>;                                                   // ADR-013
    pub fn evaluate(&mut self, store: &str, queries: &Path, calibrate: bool) -> Result<EvalReport, Error>;
}
```

### Rules every implementation keeps

- `search`, `read` and `context` filter by scope **before** ranking or reading
  (X1); a `read` outside the scope returns `scope.denied`.
- `context` never loads the embedding model, never syncs and never runs past
  `deadline`; on any internal error it returns an empty `ContextResult`
  (C6). `conventions` is set only the first time a `session_id` (or, without
  one, the process) gets a non-empty result (C5a).
- A write targets exactly one store; `store == None` means the default store
  (M4).
- `append_log` to a `personal` store applies immediately; every other write,
  and any write to a `team` store, returns a pending proposal (W2, W5).
- Writes sync before and after (Y3, Y2) and hold the store lock (ADR-010).
- Credentials passed to `ConnectStep::finish` go straight to the credential
  store and never appear in a result, a log or an error.

## Example

```rust
let mut ws = open_workspace(None)?;
let res = ws.context("Prépare la relance TVA pour Boulangerie Dupont",
                     None, Some("s1"), Duration::from_millis(1500));
// res.detections[0].drawer.to_string() == "cabinet-exemple:clients/c042"
// res.blocks[0].sections == ["Identité", "Points d'attention", "Échéances"]
let drawer: DrawerRef = "cabinet-exemple:clients/c042".parse()?;
let out = ws.append_log(&drawer, "Relance TVA préparée.")?;
// team store: out.applied == false, out.proposal.unwrap().status == Pending
let done = ws.confirm(&out.proposal.unwrap().id)?;   // after the user said yes
assert!(done.applied);
```

## Error cases

| Condition | Code |
|---|---|
| Unknown store name or drawer id | `store.unknown`, `drawer.unknown` |
| Read or search outside the scope | `scope.denied` |
| Schema invalid (S6) | `schema.invalid` (no write happens) |
| Metadata fails validation on create | `metadata.invalid` |
| Confirming a proposal whose base changed | not an error: returns a new pending proposal, or the old one marked `Stale` (Y4b) |
| Proposal expired or unknown | `proposal.unknown` |
| Write into a drawer purged elsewhere | `drawer.purged` (Y4e) |
| Write holding an explicit link that resolves to nothing | `link.unresolved` (L2) |
| Store lock not obtained within 10 s | `store.busy` |
| Remote unreachable | not an error: `WriteOutcome.pushed == false`, change queued (Y4c) |
| History rewritten outside tiroir | `sync.foreign-rewrite` (ADR-010) |
| Credential rejected by the host | `remote.auth` |

## Changing this contract

Lanes are building against this. A change needs agreement from every party
listed above, and the lanes must be told; a silent change produces work that
cannot be integrated.
