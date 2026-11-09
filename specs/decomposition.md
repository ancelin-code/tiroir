# Decomposition: tiroir v1

**Status:** draft (the `retrieval` cut, 2026-11-09)
**Approved by:** Ancelin Serre, 2026-11-04 (S7 added to `retrieval`); first approved 2026-10-22 (milestone plan and the skeleton's cut)

## Source

- Requirements: [`specs/prd.md`](prd.md) (approved 2026-11-04).
- Decision records: [`specs/decisions/`](decisions/), ADR-001 to ADR-016
  (accepted 2026-10-22). The skeleton relies most on ADR-002 (Python, tooling,
  container), ADR-003 (store format), ADR-004 (server database), ADR-005 and
  ADR-007 (index, lexical retrieval), ADR-009 (process model), ADR-010 (Git on
  the server), ADR-015 (authentication) and ADR-016 (deployment).
- Contracts: [`specs/contracts/`](contracts/): `schema.md`,
  `store-layout.md`, `core-api.md`, `mcp-tools.md`, `http-routes.md`,
  `cli.md`. `claude-code-hook.md` is not used before the retrieval milestone.
- The skeleton was cut from an empty repository. The `retrieval` cut starts
  from `develop` after v0.1.0 and from the
  [skeleton's review note](milestones/skeleton.md), whose "Carried over" list
  it takes up; it relies most on ADR-005 to ADR-009 and ADR-013, and on the
  `claude-code-hook.md`, `mcp-tools.md` and `core-api.md` contracts.

## Milestones

Delivered in four end-to-end slices, riskiest first, with a review after each
(agreed with the project owner on 2026-10-22).

**Documentation, every milestone.** A milestone is not delivered until the
user documentation site documents what it adds (AGENTS.md), so each exit
below includes it, and each cut plans it twice: every task that changes
user-visible behaviour updates or adds its page in the same change, and the
cut ends with one documentation task that owns what no single task does (the
roadmap, the changelog's `[Unreleased]` section, the README's status, pages
spanning the milestone) and reads the whole site against what the milestone
now does. The skeleton did this with `docs-001` and `docs-002`; the
retrieval cut does it with `guides-001`.

### skeleton

Retires the risks nothing else can retire on paper: a remote MCP connector
signed in through tiroir's own OAuth server and reached by Claude Desktop over
HTTPS, a container deployment, and the store-to-search path through Git and
the index. Everything later builds on these pieces.

**Exit:** On a VPS with a domain name, `docker compose up -d` and `tiroir admin init` give a server answering over HTTPS; the administrator creates a personal store from the `accounting-firm` preset; in Claude Desktop, after adding the server as a custom connector and signing in, the member appends a log entry to a client's drawer and finds it with a keyword search within 2 seconds; the entry is one commit, with tiroir's trailers, in the store's history.
**Requirements:** A1 (part), A2 (part), A4 (part), A5, M1 (part), M3 (part), S1 (part), S2 (part), S4 (part), S6 (part), R1 (part), R2 (part), R3, R6, R7 (part), W1, W4 (part), Y1 (part), Y2, Y5 (part), U1 (part), U4 (part), U5 (part), D1 (part), D3
**Epics:** foundation, store, search, server, deploy, docs

### retrieval

Semantic search and the default model are where retrieval quality is decided,
and context injection (the Claude Code hook as an `mcp_tool` call, the memory
skill) is the second host integration to prove. Both need the skeleton's
store, index and MCP endpoint.

When this milestone is cut, its evaluation also settles four questions that
the review of `search-001` (PR #18) left open against the literature:

- **French stemmer:** Snowball (ADR-007) against a light, inflection-only
  stemmer, which Savoy's CLEF experiments found as good for French, on the
  French set.
- **Fusion:** RRF with k = 60 (ADR-007, Cormack et al. 2009) against a convex
  combination of normalised scores, which Bruch et al. (2023) found better and
  less parameter-sensitive with few labelled queries; and k itself.
- **Lexical floor:** the "half the content terms" rule has no published
  grounding beyond `minimum_should_match` practice; tune it on the negative
  queries.
- **Identifier joining:** digit runs split by single spaces join across
  neighbouring numbers (`123 456 789 2 dossiers` gives `1234567892`); decide
  whether to bound the join, for example to SIREN and SIRET lengths.

**Exit:** On the skeleton's server, the evaluation command reports recall@5, MRR and negative false positives for lexical, semantic and hybrid retrieval on both bundled sets, hybrid at least as good as each alone; the default model is the evaluation's winner within the 4 GB budget; in Claude Code with the plugin installed, a prompt naming a client injects that client's summary within 300 ms at p95; in Claude Desktop, the memory skill makes the agent use tiroir on a scripted set (C7) and record new facts (W7); the documentation site describes what the milestone adds, for members and administrators.
**Requirements:** R1, R2, R4, R4a, R5, R7, S3, S4, S7, C1, C1a, C2, C3, C4, C5, C5a, C5b, C5c, C6, C7, W7, U2, V1, V2, V3, V4, P1, P2, P3, P4, P6, D1 (part)
**Epics:** semantic, context, skill, presets, eval, bench, guides

### team

Turns a one-person server into an organisation's: members, per-store access
and its isolation guarantees, confirmations, and the init interview that lets
a non-developer shape their own store.

**Exit:** Two members with different grants use one server from Claude Desktop: each reaches only their granted stores (checked by the isolation property test), a write to the team store is shown and recorded only after confirmation, concurrent writes lose nothing, and a non-developer completes the init interview into a store the administrator created; the administrator manages all of this from the web administration page; the documentation site describes what the milestone adds, for members and administrators.
**Requirements:** A2, A3, A4, M2, M3, M4, M5, S1, S2, S6, I1, I2, I3, X1, X1a, X2, X3, X4, W2, W3, W4, W5, W6, Y1, Y4, Y4a, Y4b, Y4f, Y4g, U1, U3 (part), U4, U5, P7, H1
**Epics:**

### operations

What makes a server safe to keep for years: erasure, links, schema
evolution, mirrors and clones, backup, restore and upgrade, and the
documentation that lets others run it.

When this milestone is cut, it also measures two costs of keeping each store
as a Git repository, a choice re-examined and kept on 2026-10-27 (ADR-010).
Unreasonable numbers reopen ADR-010:

- **Purge:** the time of a drawer purge (ADR-011: `git filter-repo`, clean-up
  and the force-push to one mirror) on a store of P6's size.
- **Growth:** the repository's size on disk and the time of one log append
  once a drawer holds a few thousand entries, before and after a repack.

**Exit:** A purge removes a drawer from the store, its history, the index and a mirror, and masks links to it; a migration moves drawers with links still resolving; a technical member clones a store read-only; a server is backed up, restored on another machine and upgraded to a new version with its data migrated; a fresh administrator follows the documentation from a new VPS to a connected member in under 30 minutes; the documentation site describes what the milestone adds, for members and administrators.
**Requirements:** A1, A6, A7, E1, E2, E3, E4, E5, L1, L2, L3, L4, L5, L6, I4, I5, Y4d, Y4e, Y5, Y6, Y7, S5, U3, P5, D1, D2, H2, H3
**Epics:**

## The `retrieval` cut

### What it carries over

From [the skeleton's review note](milestones/skeleton.md), "Carried over":

- the four retrieval questions (stemmer, fusion, floor, identifier joins):
  `eval-003`, on the sets of `eval-002`;
- reporting a missing vector channel accurately, never as "pending":
  `semantic-003`;
- fixing `docs/connect/claude-desktop.md` with the observed dialog:
  `guides-001`, the milestone's documentation pass;
- the start-time and CI check that SQLite has FTS5: `semantic-002`;
- whether Claude Desktop declares elicitation, and whether a token refresh
  happens: observed in `guides-002`'s exit check;
- deferred from `search-001`: the indexer and rebuild lock and blob reads on
  rebuild (`semantic-002`), the date filter on undated files
  (`semantic-003`);
- deferred from `server-004`: store identifiers outside the quoted block
  (`context-003`).

Already done since the review: the README status line, the v0.1.0 release.
Not taken by this cut: amending ADR-015 with the observed client
identification, which is `etabli-spec`'s.

### Points for the contracts' owner

The cut found three places where a contract does not fit what the tasks must
build. Each task follows the line below and names the amendment; the
contracts are to be amended through `etabli-spec` before or with those tasks:

- `claude-code-hook.md` names `tiroir.adapters.claude_code` as the renderer
  of the context block, but `tiroir.server` may not import an adapter
  (ADR-013's independence rule); `context-003` renders it in `tiroir.server`.
- `core-api.md` types `evaluate` and `calibrate`'s query set as a `Path`; a
  member's set arrives as text through `tiroir_store` (V4); `eval-001` takes
  the set's text.
- `cli.md` gains `tiroir admin stores presets` to list presets and their
  origin (S7, `presets-002`).

## Epics

The epics of the `retrieval` milestone come first; those of the closed
`skeleton` milestone follow, from `foundation` on.

### semantic

Search finds by meaning as well as by keyword: chunks are embedded on the
server by an ONNX model from a registry of multilingual candidates, or by an
OpenAI-compatible service chosen per store, and lexical and vector candidates
are fused with abstention per channel (ADR-005, ADR-006, ADR-007).

- `semantic-001` - Embed text on the server with ONNX Runtime, from a registry of candidate models
- `semantic-002` - Store chunk vectors in the index and embed new chunks in the background
- `semantic-003` - Search semantically and fuse lexical and vector ranks
- `semantic-004` - Choose a store's embedding model or an external service, with a background re-index

### context

A prompt that names a drawer brings that drawer's summary into the agent's
context, from detection by declared names or working directory, through the
`tiroir_context` tool, to the Claude Code plugin's prompt hook, failing open
within its deadline (ADR-008, ADR-009, ADR-013).

- `context-001` - Detect the drawers named in a text or matched by the working directory
- `context-002` - Assemble the context of a request within its deadline
- `context-003` - Serve tiroir_context and the memory skill's tool on the MCP endpoint
- `context-004` - Ship the Claude Code plugin with its prompt hook

### skill

Each member downloads a memory skill generated from the schemas of their own
stores, which tells the agent when to read and write memory on hosts without
hooks, and knows when it is out of date (ADR-013).

- `skill-001` - Generate each member's memory skill from the schemas of their stores
- `skill-002` - Serve the member's account page with the memory skill download

### presets

Both presets ship, and an administrator adds their own in one folder of the
server, used by name like a bundled one (S4, S7).

- `presets-001` - Write the developer preset with its synthetic dataset
- `presets-002` - Let the administrator add their own presets in one folder of the server

### eval

Retrieval and detection are measured on judged query sets shipped with each
preset, a store's threshold is calibrated from them, and the default model
and retrieval parameters are chosen on that evidence (V1 to V4, R4a).

- `eval-001` - Evaluate retrieval and detection on a judged query set, and calibrate a store's threshold
- `eval-002` - Write the judged query sets of both presets
- `eval-003` - Compare the candidate models, choose the default, and settle the retrieval parameters

### bench

The performance budgets are measured on generated stores of the reference
and the large size, by one command (P1 to P4, P6).

- `bench-001` - Benchmark the server against the performance budgets on generated stores

### guides

The documentation site describes everything the milestone adds, from the
pages each task wrote to a final pass over the whole site (roadmap,
changelog, README, per-host capabilities, the Claude Desktop guide), and the
milestone's exit is checked from a written script, C7 and W7 included.

- `guides-001` - Bring the documentation site up to date with the retrieval milestone
- `guides-002` - Write the retrieval exit check with its scripted conversations, and run it


### foundation

The Python project exists with its tooling, layout, dependency rule and CI, so
every later task starts from the same commands and checks (ADR-002, ADR-013).

- `foundation-001` - Bootstrap the Python project, its tooling and CI

### store

A store is a bare Git repository written by tiroir alone: its schema is loaded
and validated, a store is created from the `accounting-firm` preset, and a log
entry is appended as one commit with tiroir's trailers (ADR-003, ADR-010).

- `store-001` - Load and validate the store schema
- `store-002` - Create, read and write stores as bare Git repositories
- `store-003` - Write the accounting-firm preset with its synthetic dataset

### search

Every store has a derived SQLite index kept up to date after each commit, and
keyword search returns cited results with French normalisation and exact
identifiers (ADR-005, ADR-007, lexical half).

- `search-001` - Index stores and search them by keyword

### server

The server runs as one process with its database, its first administrator,
OAuth sign-in for MCP clients, and an MCP endpoint through which a signed-in
member lists drawers, appends to a log and searches (ADR-004, ADR-009,
ADR-015).

- `server-001` - Run the server process with its database and first administrator
- `server-002` - Sign members in and act as the OAuth authorization server
- `server-003` - Expose the core API as a member-scoped facade, with store creation from a preset
- `server-004` - Serve the MCP endpoint with search, read and log tools

### deploy

The server ships as a container image behind Caddy, and an administrator can
follow a written guide from a fresh VPS to Claude Desktop finding a note
(ADR-016).

- `deploy-001` - Build the container image and the Compose stack behind Caddy
- `deploy-002` - Write the skeleton installation guide and run the exit check

### docs

The user documentation is a Zensical site published to GitHub Pages, which every
later milestone updates (AGENTS.md, "User documentation").

- `docs-001` - Publish the user documentation as a Zensical site on GitHub Pages
- `docs-002` - Polish the documentation site and document custom schemas for administrators

## Parallelism

The `retrieval` cut. (The skeleton's ran `foundation-001` alone first, then up
to three benches; its critical path was `foundation-001` → `store-001` →
`store-002` → `search-001` → `server-003` → `server-004` → `deploy-002`.)

**Run as:** benches

- **No task runs alone.** `semantic-001` is the only task that edits
  `pyproject.toml` and `uv.lock` (it adds ADR-002's embedding dependencies),
  so the lock file needs no `parallel: false`.
- **The core facade serialises six tasks.** `semantic-002`, `semantic-003`,
  `semantic-004`, `context-002`, `skill-001` and `eval-001` all edit
  `src/tiroir/core/api.py`, and most of them `types.py` and `__init__.py`;
  each pair declares `conflicts_with`. They are where the cut serialises,
  whatever the dependencies allow.
- **`server.db` migrations:** `semantic-004`, `skill-001` and `eval-001` each
  add one and edit `serverdb.py`; whichever merges later takes the next free
  number.
- **Other shared files:** `cli/admin.py` (`semantic-004`, `presets-002`,
  `eval-001`); `server/mcp.py` and `test_mcp_tools.py` (`context-003`,
  `eval-001`); `lexical.py` and the hybrid tests (`semantic-003`,
  `eval-003`); `indexer.py` (`semantic-002`, `semantic-004`); `mise.toml`
  (`semantic-001`, `bench-001`); `zensical.toml`'s nav (`semantic-003`,
  `semantic-004`, `context-004`, `skill-002`, `presets-001`, `eval-001`,
  `eval-003`, `guides-001`: each adds a page); `docs/reference/cli.md`
  (`semantic-004`, `presets-002`, `eval-001`). Each pair declares the
  conflict.
- **Ready at the start:** `semantic-001`, `context-001`, `skill-001`,
  `presets-001` and `presets-002`, all free of conflicts with each other. Then
  `eval-002` (after `presets-001`) and `semantic-002` (after
  `semantic-001`, and not beside `skill-001`).
- **Two chains meet at `eval-003`:** the semantic chain through `eval-001`,
  and the context chain `context-001` → `context-002` → `context-003` →
  `bench-001`. `eval-003` needs both, and the judged sets of `eval-002`.
- **The documentation pass waits for every user-visible task:** `guides-001`
  depends on each task that adds a page, so it reads the site once it is
  complete; `guides-002` runs the exit check after it.

## Critical path

`semantic-001` → `semantic-002` → `semantic-003` → `semantic-004` (held by
its conflict with `semantic-003`) → `eval-001` → `eval-003` → `guides-001`
→ `guides-002`

The context chain (`context-001` → `context-002` → `context-003` →
`bench-001`) runs beside it, but `context-002` competes with the semantic
tasks for `api.py`, so the facade, not the dependencies, sets the pace.
