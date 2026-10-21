# tiroir — Requirements

**Status:** draft
**Approved by:** <pending>

## Problem

AI agents start every session from scratch, and the memory tools that exist
either hard-code one organisation of memory (usually "coding projects"), hide
it in opaque stores, send it to a cloud, or mix contexts that must stay apart.
Professionals bound by confidentiality, such as accountants, lawyers or
consultants, need a memory organised the way they work (one drawer per client), kept
in files they own, strictly isolated between clients, and usable from Claude
Desktop by people who do not use a terminal.

## Vocabulary

The product vocabulary used in every artifact, command and tool name. The
metaphor is kept.

| Term | Meaning |
|---|---|
| **Store** | One Git repository holding one memory: an organisation's, a team's, or one person's. |
| **Drawer type** | A user-declared kind of scope (`client`, `repo`, `engagement`…) with its metadata fields, layout, templates, detection names and injection policy. |
| **Drawer** | One instance of a drawer type: client C042, repository `api-gateway`. |
| **Shared space** | Store-level content that belongs to no drawer: procedures, conventions, templates, preferences, calendars. |
| **Summary** | The one curated document of a drawer, rewritten only after user confirmation. |
| **Log** | The dated, append-only entries of a drawer. |
| **Schema** | The configuration file declaring drawer types, layout, metadata, templates, detection, injection policy and memory language. |
| **Preset** | A ready-made schema with synthetic example content. |
| **Active drawers** | The drawers a request is currently scoped to: those explicitly named in the request, or selected by the user or agent. |
| **Host** | An agent application: Claude Code, Claude Desktop. |
| **Adapter** | The host-specific layer: install, configuration wiring, lifecycle hooks. |

## Users

- **Solo developer**: memory per repository or project, in Claude Code.
- **Professional, non-developer** (accountant, lawyer, consultant): one drawer
  per client, confidential data, often a memory language other than English.
  Starts in Claude Desktop and may move to Claude Code later.
- **Small team**: one store shared through a private Git host.

## Outcomes

Each outcome is observable. "Must" outcomes define v1; "Should" outcomes are
built after the Must set and may slip to a later release.

### Schema and presets (Must)

- **S1.** A store is configured by one declarative schema file. A drawer type
  declares: its name; where its drawers live in the folder layout; its
  metadata fields; its summary and log templates; the fields and aliases that
  name a drawer of this type in text (detection names); and its injection
  policy (which parts of the summary are injected and a size cap).
- **S2.** Metadata fields support at least: text, number, date, boolean, enum,
  list of text, and required versus optional. Validation reports every
  violation with the file, the field and the expected type. Computed fields
  are not supported.
- **S3.** The schema declares the store's memory language. It selects the
  templates' language, the language the agent is instructed to write memory
  in, and the lexical-search behaviour (see R3).
- **S4.** Two presets ship: `developer` (English) and `accounting-firm`
  (French). Each contains a schema, templates, conventions and a synthetic
  dataset of at least 20 drawers with summaries and logs. No real person or
  company data appears in the public repository.
- **S5.** A store is fully usable without tiroir installed: every summary, log
  and shared document is a Markdown file a person can read and edit in any
  text editor, and the store's root holds an entry document that explains the
  layout and lists the drawers.
- **S6.** A schema error never corrupts data: tiroir refuses to write to a
  store whose schema does not validate, and `doctor` names the problem.

### Init and migration (Must)

- **I1.** An init skill interviews the user in their language, proposes a
  schema (starting from a preset when one fits), shows what it will create,
  and writes the schema, templates and conventions only after the user agrees.
- **I2.** A non-developer completes the init interview in Claude Desktop and
  ends with a store that passes `doctor`, without opening or editing a
  configuration file.
- **I3.** Re-running init on an existing store never overwrites user content:
  every change it would make is shown as a proposal and applied only after
  confirmation.
- **I4.** A schema migration supports at least: adding a field (with a default
  or left empty), renaming a field, renaming a drawer type, and changing the
  folder layout. A dry run lists every file it would create, move or modify,
  and changes nothing.
- **I5.** Applying a migration produces one atomic change in the store's
  history, after which `doctor` passes and no summary or log content has been
  lost (checked by comparing content before and after, modulo the declared
  changes).

### Retrieval (Must)

- **R1.** Search combines lexical and semantic retrieval, plus filters on
  drawer type, drawer, metadata fields, entry kind and date range.
- **R2.** Lexical search finds exact identifiers, numbers and proper nouns: a
  query for a company registration number, an invoice number or a surname
  ranks the entry containing it first in the bundled evaluation set.
- **R3.** With French as memory language, lexical search is insensitive to
  diacritics and case and matches inflected forms: `echeance` finds
  `échéance`, `déclarations` finds `déclaration`.
- **R4.** Semantic search uses an embedding model that runs on the user's
  machine and handles the store's memory language (multilingual for French).
  The user can switch model through configuration; switching triggers a full
  re-index and applies the abstention threshold calibrated for that model.
- **R5.** Search abstains: when no result clears the confidence threshold, it
  returns no results and says so, rather than returning the closest match.
- **R6.** Every result carries its drawer (or shared space), file path, entry
  kind and date, so the agent can cite it and the user can open it.
- **R7.** The index is derived: deleting it and running the index command
  rebuilds identical search results. Changes received from the remote are
  reflected in the next search without a manual re-index.

### Isolation (Must)

- **X1.** When active drawers are set, every read and search returns content
  only from those drawers and from the shared space. This holds for every
  read path (search, summary read, log read, injection).
- **X2.** Searching across drawers requires an explicit request (a distinct
  parameter or command), and each result in such a search is labelled with
  its drawer.
- **X3.** X1 and X2 are verified by an automated property test over generated
  stores and queries, run in continuous integration: no scoped read ever
  returns content from a drawer outside the active set.
- **X4.** The guarantee is documented precisely: tiroir never returns another
  drawer's content in a scoped request; it cannot prevent a host with
  filesystem access, or a user mentioning two clients in one conversation,
  from bringing both into the context.

### Context (Must)

- **C1.** Drawer detection finds the drawers explicitly named in a piece of
  text, by their declared detection names (identifier fields, names,
  aliases). Several named drawers are all detected. Each detection reports the
  text that matched.
- **C2.** A name that matches more than one drawer is reported as ambiguous
  and nothing is injected for it.
- **C3.** Detection does not guess: text that names no drawer detects none,
  measured on the bundled evaluation set as zero false detections on its
  negative cases.
- **C4.** Injected context is the injection-policy part of each detected
  drawer's summary, within the size cap, framed as reference data that the
  agent must not treat as instructions.
- **C5.** At session start (on hosts that support it) tiroir provides the
  store's conventions and the list of drawers with their detection names,
  within a size cap set in the schema.
- **C6.** Any failure, timeout or empty detection injects nothing and never
  blocks or delays the user's prompt beyond the latency budget (P1).
- **C7.** On a host without lifecycle hooks (Claude Desktop), the same context
  is available on demand: the agent is told by the MCP server how and when to
  call it, and documentation provides a project-instructions snippet that
  makes the agent load it. Acceptance: on a scripted set of at least ten
  prompts naming a client of the synthetic accounting store, the agent calls
  tiroir and uses that client's summary in at least nine.

### Writing (Must)

- **W1.** An agent can append a log entry to a drawer. The entry is dated,
  follows the log template, and existing entries are never modified.
- **W2.** An agent can propose a summary update. The proposal is shown as a
  diff and is applied only after explicit user confirmation; a proposal not
  confirmed changes nothing.
- **W3.** An agent or user can create a drawer from its type's template, with
  metadata validated against the schema before anything is written.
- **W4.** A successful write is visible to the next search.

### Erasure (Must)

- **E1.** A drawer can be purged: its files are removed from the working tree,
  the index and the entire history of the store, locally and on the Git
  remote. A dry run lists what will be removed; the purge runs only after
  explicit confirmation naming the drawer.
- **E2.** After a purge, synchronising any other clone of the store never
  reintroduces the purged content: a clone still holding it is detected and
  told how to discard it, and tiroir refuses to push it back.
- **E3.** Purging a drawer is the only operation that removes log entries.

### Sync (Must)

- **Y1.** tiroir manages the store's Git repository autonomously and
  transparently: committing, pulling, pushing and conflict handling happen
  without user action. The user never runs, reads or needs to understand a Git
  command, and the documentation never asks them to.
- **Y2.** Every write is recorded in the store's history and pushed to the
  remote when one is reachable; when it is not, writes keep working locally
  and are pushed on the next successful sync.
- **Y3.** tiroir pulls remote changes at session start and before writing.
- **Y4.** Concurrent edits never lose data. Log entries written on two
  machines are both kept. Two diverging edits of the same summary are both
  preserved and reported to the user for resolution.
- **Y5.** Commit messages, logs and error output contain no memory content: no
  summary or log text, no metadata values. They may contain operation types
  and drawer identifiers.
- **Y6.** The remote is provider-agnostic: any Git remote reachable over SSH
  or HTTPS works (for example a self-hosted Forgejo or Gitea, GitLab, GitHub,
  or a bare repository on a server the user controls). Documentation gives a
  step-by-step recipe for a self-hosted Forgejo, the recommended option for
  confidential data, and for one hosted provider.
- **Y7.** Connecting a machine to an existing store takes one documented step
  on the Git host (such as approving the machine) and no manual handling of
  keys or tokens.
- **Y8.** Only tiroir writes to the store's shared history. The credential that
  grants write access to the remote is created and held by tiroir on each
  machine; the user is never given it or asked to handle it.
- **Y9.** Edits made to store files outside tiroir (for example in a text
  editor) are detected at the next tiroir operation and reported with the
  files concerned. Until the user confirms them through tiroir, they are not
  committed, not pushed, and not used by retrieval or injection.
- **Y10.** An outside edit that breaks an invariant (a modified or deleted log
  entry, an invalid schema, metadata that fails validation) cannot be
  confirmed; tiroir offers to restore the last recorded version of the file.

### Surfaces (Must)

- **U1.** An MCP server exposes the read, search, context and write operations
  above and works in Claude Desktop and Claude Code. Its tool count stays small
  enough that its descriptions cost under 2,000 tokens of context.
- **U2.** A Claude Code adapter installs in one command and wires session-start
  context and per-prompt detection and injection.
- **U3.** A CLI covers: init from a preset, index, search, validation
  (`doctor`), sync, migrate, purge and install.
- **U4.** A non-developer installs tiroir for Claude Desktop without a terminal
  beyond copy-pasting documented commands, and preferably with none.
- **U5.** The adapter boundary is documented as a contract, and the core
  (schema, storage, index, retrieval, detection, sync) has no dependency on
  any host. Checked by a test that imports the core with no adapter present.

### Evaluation (Must)

The brief lists this as Should. It is raised to Must because the abstention
threshold depends on the embedding model and must be calibrated per model
(see `docs/research/prior-art.md`).

- **V1.** An evaluation command runs a judged query set against a store and
  reports recall@k, MRR, and the false-positive rate on negative queries, for
  lexical-only, semantic-only and hybrid retrieval, and for drawer detection.
- **V2.** Each preset ships a judged query set including negative queries
  (questions the store cannot answer).
- **V3.** On both bundled sets, hybrid retrieval scores at least as high as
  lexical-only and semantic-only on recall@5 and MRR, and higher on at least
  one of them.
- **V4.** Users can run the evaluation on their own store with their own query
  set.

### Performance (Must)

Measured on an ordinary laptop (4 CPU cores, 8 GB RAM, no GPU) with a store of
500 drawers and 10,000 log entries.

- **P1.** Per-prompt detection and injection: p95 ≤ 300 ms once the tiroir
  process is running; a hard ceiling of 2 s after which nothing is injected.
- **P2.** Hybrid search: p95 ≤ 500 ms once the process is running.
- **P3.** Full index rebuild ≤ 15 minutes; reflecting one changed file ≤ 2 s.
- **P4.** Resident memory of the running server, model loaded, ≤ 1 GB.
- **P5.** A developer goes from install to a working store from a preset,
  searched from Claude Code, in under 10 minutes, excluding the one-time model
  download.

### Platforms and documentation (Must)

- **D1.** tiroir runs on macOS, Windows and Linux, verified by continuous
  integration on all three.
- **D2.** Documentation lets a user adopt tiroir without reading code: install
  per host, the schema reference, both presets, the isolation guarantee and
  its limits (X4), erasure, sync and conflicts, and the per-host capability
  table (what works with and without hooks).
- **D3.** The project is open source under Apache-2.0, recorded in a
  decision record.

### Should

- **H1.** Team onboarding and offboarding are documented: adding a member to a
  store, removing one, and what removal does and does not revoke.
- **H2.** Writes refuse content matching recognised credential patterns, and
  say why.
- **H3.** A store's layout stays compatible with the Agent Memory Repo format
  (an entry document loaded at session start, `[[path]]` links), so other
  agents can use it without tiroir.

## Invariants

These hold for every task and every release.

- Plain Markdown files in a Git repository are the only source of truth;
  every index is derived and rebuildable from them.
- No network traffic other than to the store's Git remote and the one-time
  download of models from a documented source. No telemetry.
- Scoped reads never cross drawers (X1).
- Log entries are never modified, and only a purge removes them (W1, E3).
- A summary never changes without explicit user confirmation (W2).
- No memory content in commit messages, logs or error output (Y5).
- Only tiroir writes to a store's shared history (Y8).
- The core never depends on a host (U5).
- Organisation of memory is configuration: adding a drawer type or field never
  requires a code change.

## Out of scope

- Automatic capture or compression of whole sessions.
- Document ingestion (PDF, email, spreadsheets, accounting exports).
- A web or desktop UI of tiroir's own.
- Per-drawer permissions: access control is per store, by the Git host.
- Adapters for hosts other than Claude Code (the contract is designed, U5).
- Any hosted or SaaS offering.
- **Server-side enforcement** of the invariants by the Git remote (rejecting a
  push that modifies a log entry, for example). Planned with server mode as a
  complement to Y8–Y10.
- **The self-hosted server mode** (brief §9). v1 is local-first: each machine
  holds a clone, its own index and a local MCP server. The design must not
  preclude a later server mode, which gets its own requirements revision.
- Encryption at rest: the store relies on the operating system's disk
  encryption and the Git host's protections; documentation says so.
- LLM-driven memory rewriting, deduplication or contradiction resolution.
- Erasure of a single log entry (only whole-drawer purge, E1).
- Running a private Git host: the user provides one; documentation lists
  suitable options.

## Assumptions

- Non-developers on Claude Desktop use macOS or Windows, since Claude Desktop
  does not ship for Linux. The Desktop path is verified on both; Linux is a
  target for Claude Code and servers.
- On-demand memory in Claude Desktop (C7) is acceptable for v1; users who move
  to Claude Code get hook-based injection there.
- A store holds at most a few thousand drawers and tens of thousands of
  entries; no approximate-nearest-neighbour index is needed at that size.
- Each machine has Git available, or tiroir ships what it needs to run Git
  operations itself. Which one is a design decision.
- The private Git host supports the history rewrite and forced update that a
  purge requires (E1). If branch protection forbids it, the purge procedure
  documents how to lift it temporarily.
- Entry kinds in v1 are summary, log and shared-space documents. Further
  user-declared kinds are deferred.
- Legal retention obligations (how long records must be kept) are the
  user's responsibility; tiroir provides the purge mechanism, not the policy.

## Open questions

None at this stage.

## Sources

- `brief.md` — product brief.
- `docs/research/prior-art.md` — review of agentcairn, Cairn, agent-memory-kit,
  Basic Memory, claude-mem, agentmemory and the Agent Memory Repo format.
