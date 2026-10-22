# Decomposition: tiroir v1

**Status:** approved
**Approved by:** Ancelin Serre, 2026-10-22 (milestone plan and the skeleton's cut)

## Source

- Requirements: [`delivery/prd.md`](prd.md) (approved 2026-10-22).
- Decision records: [`delivery/decisions/`](decisions/), ADR-001 to ADR-016
  (accepted 2026-10-22). The skeleton relies most on ADR-002 (Python, tooling,
  container), ADR-003 (store format), ADR-004 (server database), ADR-005 and
  ADR-007 (index, lexical retrieval), ADR-009 (process model), ADR-010 (Git on
  the server), ADR-015 (authentication) and ADR-016 (deployment).
- Contracts: [`delivery/contracts/`](contracts/): `schema.md`,
  `store-layout.md`, `core-api.md`, `mcp-tools.md`, `http-routes.md`,
  `cli.md`. `claude-code-hook.md` is not used before the retrieval milestone.
- The repository holds no code yet: everything below is built from scratch.

## Milestones

Delivered in four end-to-end slices, riskiest first, with a review after each
(agreed with the project owner on 2026-10-22).

### skeleton

Retires the risks nothing else can retire on paper: a remote MCP connector
signed in through tiroir's own OAuth server and reached by Claude Desktop over
HTTPS, a container deployment, and the store-to-search path through Git and
the index. Everything later builds on these pieces.

**Exit:** On a VPS with a domain name, `docker compose up -d` and `tiroir admin init` give a server answering over HTTPS; the administrator creates a personal store from the `accounting-firm` preset; in Claude Desktop, after adding the server as a custom connector and signing in, the member appends a log entry to a client's drawer and finds it with a keyword search within 2 seconds; the entry is one commit, with tiroir's trailers, in the store's history.
**Requirements:** A1 (part), A2 (part), A4 (part), A5, M1 (part), M3 (part), S1 (part), S2 (part), S4 (part), S6 (part), R1 (part), R2 (part), R3, R6, R7 (part), W1, W4 (part), Y1 (part), Y2, Y5 (part), U1 (part), U4 (part), U5 (part), D1 (part), D3
**Epics:** foundation, store, search, server, deploy

### retrieval

Semantic search and the default model are where retrieval quality is decided,
and context injection (the Claude Code hook as an `mcp_tool` call, the memory
skill) is the second host integration to prove. Both need the skeleton's
store, index and MCP endpoint.

**Exit:** On the skeleton's server, the evaluation command reports recall@5, MRR and negative false positives for lexical, semantic and hybrid retrieval on both bundled sets, hybrid at least as good as each alone; the default model is the evaluation's winner within the 4 GB budget; in Claude Code with the plugin installed, a prompt naming a client injects that client's summary within 300 ms at p95; in Claude Desktop, the memory skill makes the agent use tiroir on a scripted set (C7) and record new facts (W7).
**Requirements:** R1, R2, R4, R4a, R5, R7, S3, S4, C1, C1a, C2, C3, C4, C5, C5a, C5b, C5c, C6, C7, W7, U2, V1, V2, V3, V4, P1, P2, P3, P4, P6
**Epics:**

### team

Turns a one-person server into an organisation's: members, per-store access
and its isolation guarantees, confirmations, and the init interview that lets
a non-developer shape their own store.

**Exit:** Two members with different grants use one server from Claude Desktop: each reaches only their granted stores (checked by the isolation property test), a write to the team store is shown and recorded only after confirmation, concurrent writes lose nothing, and a non-developer completes the init interview into a store the administrator created; the administrator manages all of this from the web administration page.
**Requirements:** A2, A3, A4, M2, M3, M4, M5, S1, S2, S6, I1, I2, I3, X1, X1a, X2, X3, X4, W2, W3, W4, W5, W6, Y1, Y4, Y4a, Y4b, Y4f, Y4g, U1, U3 (part), U4, U5, P7, H1
**Epics:**

### operations

What makes a server safe to keep for years: erasure, links, schema
evolution, mirrors and clones, backup, restore and upgrade, and the
documentation that lets others run it.

**Exit:** A purge removes a drawer from the store, its history, the index and a mirror, and masks links to it; a migration moves drawers with links still resolving; a technical member clones a store read-only; a server is backed up, restored on another machine and upgraded to a new version with its data migrated; a fresh administrator follows the documentation from a new VPS to a connected member in under 30 minutes.
**Requirements:** A1, A6, A7, E1, E2, E3, E4, E5, L1, L2, L3, L4, L5, L6, I4, I5, Y4d, Y4e, Y5, Y6, Y7, S5, U3, P5, D1, D2, H2, H3
**Epics:**

## Epics

The epics of the `skeleton` milestone.

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

## Parallelism

**Run as:** lanes

- `foundation-001` runs alone (`parallel: false`): it creates `pyproject.toml`,
  `uv.lock`, `mise.toml`, the package layout and CI, which every other task
  builds on. It also declares every runtime dependency the skeleton needs
  (ADR-002's list, minus the embedding and purge ones), so no later task of
  this milestone edits the lock file.
- Only `server-003` edits `src/tiroir/core/__init__.py`, the public API of
  `core-api.md`; earlier core tasks put their code in sub-modules and test
  them directly, so they do not collide on it.
- `server-001`, `server-002` and `server-004` edit `src/tiroir/server/app.py`
  (routes); `server-001`, `server-002` and `server-003` edit
  `src/tiroir/core/serverdb.py`; `server-001` and `server-003` edit
  `src/tiroir/cli/admin.py`; `deploy-001` and `deploy-002` may both edit
  `mise.toml`. Each such pair declares `conflicts_with`; most are also ordered
  by dependencies, and `server-002` and `server-003`, which are not, never run
  together.
- After `foundation-001`, three lanes can start at once: `store-001`,
  `store-003` and `server-001`. Then `store-002`, `server-002` and
  `deploy-001` run in parallel.

## Critical path

`foundation-001` → `store-001` → `store-002` → `search-001` → `server-003` →
`server-004` → `deploy-002`
