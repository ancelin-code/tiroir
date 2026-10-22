# tiroir — Requirements

**Status:** approved
**Approved by:** Ancelin Serre, 2026-10-22 (revises the local-first version
approved on 2026-10-21: v1 is a self-hosted server; amended the same day:
OAuth client metadata fetching added to the network invariant)

## Problem

AI agents start every session from scratch, and the memory tools that exist
either hard-code one organisation of memory (usually "coding projects"), hide
it in opaque stores, send it to a third-party cloud, or mix contexts that must
stay apart. Professionals bound by confidentiality, such as accountants,
lawyers or consultants, need a memory organised the way they work (one drawer
per client), kept in files on a server they control, strictly isolated between
clients, and usable from Claude Desktop, the web and mobile by people who
never install software or open a terminal.

## Vocabulary

The product vocabulary used in every artifact, command and tool name. The
metaphor is kept.

| Term | Meaning |
|---|---|
| **Server** | One installation of tiroir, run by one organisation on a machine it controls (a VPS or its own computer). It holds that organisation's stores and members. |
| **Administrator** | The person who installs and runs a server, and manages its members, stores and settings. Technical. |
| **Member** | A person with an account on a server. A member uses the stores they have been granted access to. |
| **Store** | One Git repository on a server, holding one memory: an organisation's, a team's, or one person's. Access is granted per store, to members. |
| **Audience** | A store's declared readership: `personal` (one member) or `team` (several members). |
| **Drawer type** | A user-declared kind of scope (`client`, `repo`, `engagement`…) with its metadata fields, layout, templates, detection names and injection policy. |
| **Drawer** | One instance of a drawer type: client C042, repository `api-gateway`. |
| **Shared space** | Store-level content that belongs to no drawer: procedures, conventions, templates, preferences, calendars. |
| **Summary** | The one curated document of a drawer, rewritten only after user confirmation. |
| **Log** | The dated, append-only entries of a drawer. |
| **Schema** | The configuration file declaring drawer types, layout, metadata, templates, detection, injection policy and memory language. |
| **Preset** | A ready-made schema with synthetic example content. |
| **Link** | A reference from one file of a store to another: explicit (`[[path]]`) or a mention (a drawer's declared name found in the text). |
| **Active drawers** | The drawers a request is currently scoped to: those explicitly named in the request, matched from the working directory, or selected by the user or agent. They may belong to different stores. |
| **Host** | An agent application: Claude Desktop, Claude on the web and mobile, Claude Code. |
| **Adapter** | The host-specific layer: install, configuration wiring, lifecycle hooks. |
| **Mirror** | An outside Git repository to which a server copies a store, for backup or to use other tools. |

## Users

- **Professional, non-developer** (accountant, lawyer, consultant): one drawer
  per client, confidential data, often a memory language other than English.
  Uses Claude Desktop, the web or mobile, and may move to Claude Code later.
  Never installs or administers anything: a server is provided to them. The
  primary target.
- **Small team**: one server, several stores with different audiences, for
  example one for the whole company, one for its leadership and one personal
  store per member.
- **Administrator**: installs the server on a VPS or on their own machine,
  creates members and stores, and keeps the server running. May be an IT
  provider working for the professional or the team.
- **Solo developer**: administrator and only member of their own server,
  running on their machine or a VPS; memory per repository or project, in
  Claude Code.

## Outcomes

Each outcome is observable. "Must" outcomes define v1; "Should" outcomes are
built after the Must set and may slip to a later release.

### Server and access (Must)

- **A1.** tiroir is installed as one server, from a container stack and a
  documented procedure, on a Linux VPS or on the administrator's own machine
  (Linux, macOS or Windows with a container runtime). Both are the same
  software and configuration.
- **A2.** One server serves one organisation: several stores and several
  members. A member reaches only the stores they have been granted, each
  either read-only or read-write.
- **A3.** A minimal web administration page lets the administrator create and
  remove members, create stores, grant and revoke access per store, choose the
  embedding model per store (R4), configure mirrors (Y6), and see the server's
  state: version, stores, index freshness, mirror lag, model status. It shows
  no memory content.
- **A4.** Members sign in to the server to connect a host; no credential is
  typed into a conversation. Revoking a member's access, or removing the
  member, takes effect at their next request.
- **A5.** The server is reached over HTTPS only. Documentation covers
  automatic certificates for a server with a public domain name.
- **A6.** The administrator can back up a server (stores, accounts, settings)
  and restore it on another machine with documented commands. Indexes are
  rebuilt after a restore, not backed up.
- **A7.** The administrator upgrades a server to a new version with one
  documented command. Changes to stored formats are migrated automatically and
  recorded in each store's history; a failed upgrade leaves the previous
  version's data usable.

### Stores (Must)

- **M1.** A server holds several stores, each a separate Git repository with
  its own members. Each drawer belongs to exactly one store. A member can use
  several stores at the same time.
- **M2.** Each store declares its audience. A `personal` store has exactly one
  member; a `team` store any number.
- **M3.** Every search result, injected context and write confirmation names
  the store it comes from or goes to.
- **M4.** A write goes to exactly one store. When the target is not implied by
  the drawer (a new drawer, a shared-space document), it defaults to the
  member's `personal` store; writing to another store requires naming it.
- **M5.** With no active drawer, search covers the shared spaces of all the
  stores the member uses; drawer content is reached only through active
  drawers or an explicit cross-drawer search (X2).

### Schema and presets (Must)

- **S1.** A store is configured by one declarative schema file. A drawer type
  declares: its name; where its drawers live in the folder layout; its
  metadata fields; its summary and log templates, the summary being divided
  into named sections; the fields and aliases that name a drawer of this type
  in text (detection names); and its injection policy (which parts of the
  summary are injected and a size cap).
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
- **S5.** A store is usable without tiroir: a read-only clone (Y7) or a mirror
  (Y6) holds every summary, log and shared document as a Markdown file a
  person can read in any text editor or open as an Obsidian vault, and the
  store's root holds an entry document that explains the layout and lists the
  drawers.
- **S6.** A schema error never corrupts data: tiroir refuses to write to a
  store whose schema does not validate, and `doctor` names the problem.

### Init and migration (Must)

- **I1.** An init skill interviews the user in their language, proposes a
  schema (starting from a preset when one fits), shows what it will create,
  and writes the schema, templates and conventions only after the user agrees.
- **I2.** A non-developer completes the init interview in Claude Desktop or on
  the web, in a store the administrator created for them, and ends with a
  store that passes `doctor`, without opening or editing a configuration
  file.
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
- **R4.** Semantic search uses an embedding model that handles the store's
  memory language (multilingual for French). By default the model runs on the
  server. The administrator can instead select, per store, an external
  embedding service; the administration page states that the store's content
  is then sent to that service. Changing a store's model triggers a full
  re-index of that store and applies the abstention threshold calibrated for
  the new model.
- **R4a.** The default model is the one that scores best on the bundled
  evaluation sets (V1–V3) among the models that fit the server budget (P4).
  The comparison is published with the release, and repeated when a candidate
  model is added.
- **R5.** Search abstains: when no result clears the confidence threshold, it
  returns no results and says so, rather than returning the closest match.
- **R6.** Every result carries its drawer (or shared space), file path, entry
  kind and date, so the agent can cite it and the user can open it.
- **R7.** The index is derived: deleting it and running the index command
  rebuilds identical search results.

### Isolation (Must)

- **X1.** When active drawers are set, every read and search returns content
  only from those drawers and from the shared spaces of the stores holding
  them. This holds for every read path (search, summary read, log read, link
  listing, injection).
- **X1a.** A member never receives content, names or identifiers from a store
  they have not been granted, on any path, including errors and counts.
- **X2.** Searching across drawers requires an explicit request (a distinct
  parameter or command), and each result in such a search is labelled with
  its drawer.
- **X3.** X1, X1a and X2 are verified by an automated property test over
  generated sets of members, stores and queries, run in continuous
  integration: no scoped read ever returns content from a drawer outside the
  active set, nor from a store holding no active drawer, nor from a store the
  member was not granted.
- **X4.** The guarantee is documented precisely: tiroir never returns another
  drawer's content in a scoped request, nor another store's to a member
  without access; it cannot prevent a user mentioning two clients in one
  conversation from bringing both into the context, nor control what the host
  remembers by other means (its own memory, conversation history). The
  administrator, and anyone with access to the server's disk, can read every
  store.

### Context (Must)

- **C1.** Drawer detection finds the drawers explicitly named in a piece of
  text, by their declared detection names (identifier fields, names,
  aliases). Several named drawers are all detected. Each detection reports the
  text that matched.
- **C1a.** On hosts that expose a working directory, the drawer whose declared
  path contains it is detected too (a developer working in a repository).
- **C2.** A name that matches more than one drawer is reported as ambiguous
  and nothing is injected for it.
- **C3.** Detection does not guess: text that names no drawer detects none,
  measured on the bundled evaluation set as zero false detections on its
  negative cases.
- **C4.** Injected context is the injection-policy part of each detected
  drawer's summary, within the size cap, framed as reference data that the
  agent must not treat as instructions.
- **C5.** Nothing from the store is loaded at session start. The fixed cost of
  tiroir in a session that never uses it is limited to the memory skill's
  description (at most 150 tokens) and the MCP server's tool definitions and
  one-sentence instructions (U1).
- **C5a.** The store's conventions are provided the first time tiroir is used
  in a session (skill activation, first injection or first tool call), once
  per session, within a size cap set in the schema.
- **C5b.** The list of drawers is never injected wholesale; it is available on
  demand through a tool.
- **C5c.** A memory skill tells the agent when to use tiroir. Its description
  is generated from the schemas of the member's stores (drawer type names,
  shared-space topics), in the stores' memory language, and regenerated after
  a migration or a change in the member's access.
- **C6.** Any failure, timeout, unreachable server or empty detection injects
  nothing and never blocks or delays the user's prompt beyond the latency
  budget (P1).
- **C7.** On a host without lifecycle hooks (Claude Desktop, web, mobile), the
  same context is available on demand: the memory skill (C5c) is the trigger,
  and documentation provides a project-instructions snippet that reinforces
  it. Acceptance: on a scripted set of at least ten prompts naming a client of
  the synthetic accounting store, the agent calls tiroir and uses that
  client's summary in at least nine.

### Writing (Must)

- **W1.** An agent can append a log entry to a drawer. The entry is dated,
  follows the log template, and existing entries are never modified.
- **W2.** An agent can propose a summary update. The proposal is shown as a
  diff and is applied only after explicit user confirmation; a proposal not
  confirmed changes nothing.
- **W3.** An agent or user can create a drawer from its type's template, with
  metadata validated against the schema before anything is written.
- **W4.** A successful write is visible to the next search, for every member
  of the store.
- **W5.** Every write to a `team` store, log entries included, is shown to the
  user in full, with the store's name and audience, and is recorded only after
  explicit confirmation. In a `personal` store, log appends need no
  confirmation.
- **W6.** A member with read-only access to a store cannot write to it; the
  refusal says so.

### Erasure (Must)

- **E1.** A drawer can be purged: its files are removed from the store's
  repository and its entire history, from the index, and from every
  configured mirror. A dry run lists what will be removed; the purge runs only
  after explicit confirmation naming the drawer.
- **E2.** After a purge, no write reintroduces the purged content, whoever
  makes it. Copies tiroir cannot reach (read-only clones, backups and mirrors
  that refused the update) still hold it: the administration page lists the
  mirrors that did not accept the purge, and documentation states the limits
  and how to discard the other copies.
- **E3.** A single log entry or shared-space document can be purged with the
  same guarantees as a drawer (dry run, confirmation, history, mirrors, E2).
- **E4.** Purging, of a drawer or of an entry, is the only operation that
  removes log entries, and the only one that changes them (E5).
- **E5.** A purge also replaces every explicit link to the purged content, in
  every other file and in the whole history, with the same guarantees (E2).
  Its dry run lists those files, and the files that mention the purged
  drawer's names in plain text, which the purge leaves unchanged.

### Links (Must)

- **L1.** Summaries, log entries and shared documents can link to another file
  of the same store with `[[path]]`, the path relative to the store root
  without `.md`, optionally with `#heading` and `|label`. Obsidian follows
  these links when a clone or mirror of the store is opened as a vault.
- **L2.** A write holding an explicit link that resolves to nothing is refused
  and names the link. `doctor` reports broken links.
- **L3.** A drawer's declared names found in another file's text are recorded
  as mentions, with the matching rules of C1 and C2, so references by name
  are links without any syntax.
- **L4.** For a drawer or a file, the agent or user can list outgoing and
  incoming links, explicit and mentions, each with its kind and the text that
  matched. A scoped listing returns only links whose other end is in the
  active drawers or the shared space (X1); the others need the explicit
  cross-drawer request (X2). Reading, search and injection never follow a
  link.
- **L5.** A migration that moves drawers keeps every existing link resolvable
  by tiroir, including those in log entries, which are not modified.
- **L6.** Links never cross stores: a reference to another store is plain
  text.

### History and concurrency (Must)

- **Y1.** tiroir manages each store's Git repository on the server: members
  and administrators never run, read or need to understand a Git command, and
  the documentation never asks them to, except for the optional read-only
  clone (Y7).
- **Y2.** Every write is one change in the store's history.
- **Y4.** Concurrent writes, from several members or several sessions of one
  member, never lose data, and no one ever sees a Git conflict: every
  conflict reaches the user, if at all, as a proposal to confirm.
- **Y4a.** Log entries appended concurrently never conflict: every entry is
  recorded, with no user action.
- **Y4b.** A summary or shared-document change is always applied on top of the
  latest version. If that version changed since the proposal was made, changes
  to different summary sections are combined and shown for confirmation;
  changes to the same section cause the proposal to be redone against the
  latest version and shown again.
- **Y4d.** A schema migration applies to the latest state of the store and
  runs alone: writes arriving meanwhile wait for it, or are refused with a
  message asking to retry. None is lost or applied against the old schema.
- **Y4e.** A write to a drawer that was purged is refused and reported, so that
  it cannot recreate the purged drawer (E2).
- **Y4f.** Every log entry and every summary change records its author, the
  member who made it.
- **Y4g.** Y4a, Y4b and Y4d are verified by an automated test in continuous
  integration: several simulated members write concurrently, and no entry or
  confirmed change is lost.
- **Y5.** Commit messages, server logs and error output contain no memory
  content: no summary or log text, no metadata values. They may contain
  operation types, drawer identifiers and member names.
- **Y6.** The administrator can configure, per store, a mirror on any Git
  remote reachable over SSH or HTTPS (a self-hosted Forgejo or Gitea, GitLab,
  GitHub…). Every change is pushed to it; when the mirror is unreachable,
  writes continue and the push is retried, and the administration page shows
  the lag. HTTPS works through the proxy and certificate authorities
  configured on the server.
- **Y7.** A technical member can clone a store they have access to, read-only,
  with a credential of their own created from their account. Any push is
  refused.

### Surfaces (Must)

- **U1.** The server exposes an MCP endpoint with the read, search, context and
  write operations above. It works as a remote connector in Claude Desktop,
  Claude on the web and mobile, and Claude Code, after the member signs in
  (A4). Its tool count stays small enough that its descriptions cost under
  2,000 tokens of context.
- **U2.** A Claude Code adapter installs in one command on the developer's
  machine, connects to the server, and wires per-prompt detection and
  injection, and first-use conventions (C5a).
- **U3.** A CLI covers, for technical members: search, read, log, links,
  `doctor`, evaluation, migration and purge; and, for the administrator on the
  server: members, stores, access, index, backup, restore and upgrade.
- **U4.** A non-developer connects a host to the server by entering its
  address and signing in, following documented steps, without installing
  anything or using a terminal.
- **U5.** The adapter boundary is documented as a contract, and the core
  (schema, storage, index, retrieval, detection, history) has no dependency on
  any host. Checked by building and testing the core with no adapter
  present.

### Evaluation (Must)

The brief lists this as Should. It is raised to Must because the abstention
threshold depends on the embedding model and must be calibrated per model, and
because the default model is chosen from the evaluation (R4a).

- **V1.** An evaluation command runs a judged query set against a store and
  reports recall@k, MRR, and the false-positive rate on negative queries, for
  lexical-only, semantic-only and hybrid retrieval, and for drawer detection.
- **V2.** Each preset ships a judged query set including negative queries
  (questions the store cannot answer).
- **V3.** On both bundled sets, hybrid retrieval scores at least as high as
  lexical-only and semantic-only on recall@5 and MRR, and higher on at least
  one of them.
- **V4.** Members can run the evaluation on their own store with their own
  query set, and the administrator can calibrate a store's threshold from it.

### Performance (Must)

Measured on a reference server (4 vCPU, 8 GB RAM, no GPU, Linux), with a store
of 500 drawers and 10,000 log entries, and clients at most 50 ms round trip
from the server.

- **P1.** Per-prompt detection and injection, seen from the Claude Code hook:
  p95 ≤ 300 ms; a hard ceiling of 2 s after which nothing is injected.
- **P2.** Hybrid search, seen from the client: p95 ≤ 500 ms.
- **P3.** Full index rebuild of one store with the default model ≤ 15
  minutes; a write is visible to search within 2 s.
- **P4.** Resident memory of the whole server, default model loaded, ≤ 4 GB.
- **P5.** An administrator goes from a fresh VPS with a domain name to a
  member connected from Claude Desktop and searching a store created from a
  preset, in under 30 minutes, excluding DNS propagation and the one-time
  model download.
- **P6.** On a store of 2,000 drawers and 50,000 log entries (a team's memory
  after several years), P1 and P2 still hold and P4 is not exceeded; P3's
  rebuild may take proportionally longer.
- **P7.** P1 and P2 hold with 10 members sending requests concurrently.

### Platforms and documentation (Must)

- **D1.** The server runs on Linux, x86-64 and ARM64, and on macOS and Windows
  through a container runtime; the Claude Code adapter runs on macOS, Windows
  and Linux. Continuous integration verifies the server on Linux and the
  adapter on all three.
- **D2.** Documentation lets people adopt tiroir without reading code:
  - for members: connecting each host, the presets, the isolation guarantee
    and its limits (X4), stores and audiences, erasure, conflicts, and the
    per-host capability table (what works with and without hooks);
  - for administrators: installation on a VPS and on one's own machine,
    certificates, members and access, mirrors, the external embedding option
    and what it sends, backup, restore, upgrade, and disk encryption.
- **D3.** The project is open source under Apache-2.0, recorded in a
  decision record.

### Should

- **H1.** Team onboarding and offboarding are documented: adding a member,
  removing one, and what removal does and does not revoke (clones, mirrors,
  host memory).
- **H2.** Writes refuse content matching recognised credential patterns, and
  say why.
- **H3.** A store's layout stays compatible with the Agent Memory Repo format
  (an entry document loaded at session start, `[[path]]` links), so other
  agents can use a clone without tiroir.

## Invariants

These hold for every task and every release.

- Plain Markdown files in a Git repository are the only source of truth;
  every index is derived and rebuildable from them.
- The server sends nothing outside the machine it runs on except: to
  configured mirrors; a store's content to the external embedding service
  selected for that store (R4); the one-time download of models from a
  documented source; certificate issuance; and fetching the public metadata
  document of an OAuth client connecting to the server (ADR-015). No
  telemetry.
- Scoped reads never cross drawers or stores (X1), and a member never reaches
  a store they were not granted (X1a).
- Log entries are never modified, and only a purge removes them (W1, E4); a
  purge masking links to purged content is the one change it makes (E5).
- Nothing is written to a `team` store without explicit confirmation (W5).
- A summary never changes without explicit user confirmation (W2).
- No memory content in commit messages, server logs or error output (Y5).
- Only tiroir writes to a store's history.
- The core never depends on a host (U5).
- Organisation of memory is configuration: adding a drawer type or field never
  requires a code change.

## Out of scope

- Hosting tiroir for several organisations (multi-tenant service, sign-up,
  billing). v1 serves one organisation per server; the design must not
  preclude a hosted offering later.
- A tiroir that runs without a server. A server on one's own machine covers
  local use.
- Using tiroir offline.
- Writing to a store through Git: clones are read-only (Y7), and mirrors are
  outgoing only.
- A web UI for reading or editing memory. The web administration page (A3)
  manages members, stores and settings only.
- A graph view of links: v1 lists links (L4); drawing them is left to tools
  such as Obsidian.
- Per-drawer permissions: access is per store; content with a different
  readership goes in a different store.
- Single sign-on with an outside identity provider; members have accounts on
  the server.
- Adapters for hosts other than Claude (the contract is designed, U5).
- Automatic capture or compression of whole sessions.
- Document ingestion (PDF, email, spreadsheets, accounting exports).
- Encryption at rest by tiroir itself: the server relies on the encryption of
  its disk or volume; documentation says how to enable it.
- LLM-driven memory rewriting, deduplication or contradiction resolution.

## Assumptions

- Non-developers do not install servers. Until a hosted offering exists, they
  use a server installed by an administrator (an IT provider, a colleague). If
  that proves too rare, the hosted offering moves up.
- Claude Desktop, the web and mobile reach remote connectors from Anthropic's
  infrastructure, so a server used from them must be reachable from the
  internet over HTTPS. A server on the administrator's own machine serves
  Claude Code directly; reaching it from the other hosts needs a tunnel or a
  local bridge, which is a design decision.
- Hosts need a network connection anyway, so a server unreachable for a
  moment costs nothing beyond the failed request (C6).
- The administrator belongs to, or is trusted by, the organisation: they can
  read every store (X4).
- A server serves up to about 50 members and a handful of stores per member;
  a store holds at most a few thousand drawers and tens of thousands of
  entries, and no approximate-nearest-neighbour index is needed at that size.
- The reference server (P1–P7) is a common small VPS offer; a server on a
  laptop meets the same budgets when the machine is comparable.
- Entry kinds in v1 are summary, log and shared-space documents. Further
  user-declared kinds are deferred.
- Legal retention obligations (how long records must be kept) are the
  organisation's responsibility; tiroir provides the purge mechanism, not the
  policy.

## Open questions

None at this stage.

## Sources

- `docs/brief.md` — product brief (its §9 already described the server mode;
  the brief is not yet updated for this revision).
- `docs/research/prior-art.md` — review of agentcairn, Cairn, agent-memory-kit,
  Basic Memory, claude-mem, agentmemory and the Agent Memory Repo format.
- Decisions of the project owner, 2026-10-21: self-hosted server first, no
  separate local mode, embeddings on the server with an optional external
  service, read-only Git clones, a minimal web administration page, disk
  encryption only, optional outgoing mirrors.
