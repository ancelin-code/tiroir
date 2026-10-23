---
id: server-003
title: Expose the core API as a member-scoped facade, with store creation from a preset
type: feat
epic: server
depends_on: [store-002, store-003, search-001, server-001]
parallel: true
conflicts_with: [server-001, server-002]
tier: build
review: []
---

## Context

Surfaces never touch repositories, indexes or the database directly: they call
`tiroir.core` through `open_core`, `Core.member(...)` and `Core.admin(...)`,
as fixed by the [core API contract](../contracts/core-api.md). This task
assembles the pieces built by `store-001`, `store-002`, `search-001` and
`server-001` behind that API, for the operations the skeleton needs, and adds
the administration commands that create a store from a preset and grant it.

## Covers

- M1 (part): a server holds several stores, each its own repository with
  members granted per store; several stores per member are reachable through
  the API, the team milestone exercises them
- A2 (part): `grant` and `revoke` write the grants; `Core.member` resolves the
  member's stores from them at every call, and an ungranted store answers
  `store.unknown`; the isolation property test comes in the team milestone
- R7 (part): `tiroir admin index [--store] [--rebuild]`

## Scope

Files this task is expected to touch:

- `src/tiroir/core/__init__.py`: the public API of the contract that exists
  after this task: `open_core`, `Core`, `MemberContext`, `AdminContext`,
  `CoreError`, `to_json` and the shared types
- `src/tiroir/core/api.py`: `Core` (holds the data dir, the database, the
  stores and the indexer), `MemberContext` with `stores`, `list_drawers`,
  `read` (`Summary`, `Log`, `Entry`), `search` (lexical only, degraded mode
  `vectors-pending` reported), `append_log`, `status` (stores and access only),
  and `AdminContext` with `create_store`, `grant`, `revoke`, `index`, `state`
- `src/tiroir/core/types.py`: the contract's dataclasses and enums, and
  `to_json`
- `src/tiroir/core/presets.py`: load a preset directory (`presets/<name>/`)
  into the file set `create_store` takes, validating its schema with
  `tiroir.core.schema`
- `src/tiroir/core/serverdb.py`: grant and store queries if missing
- `src/tiroir/cli/admin.py`: `tiroir admin stores list|add <name> --audience
  personal|team --language <code> [--owner <handle>] [--preset <name>]`,
  `tiroir admin grant|revoke`, `tiroir admin index`
- `tests/integration/test_api.py`, `tests/integration/test_presets.py`,
  `tests/integration/test_admin_stores.py`

Out of scope:

- proposals, confirmations, summary updates, drawer creation, shared
  documents, links, migrations, purge, evaluation (later milestones); these
  methods may exist as stubs raising `CoreError("not-implemented")` only if
  the type checker needs them, otherwise leave them out
- the MCP tools (`server-004`)

## Acceptance criteria

- `tiroir admin stores add cabinet --audience personal --language fr --owner
  alice --preset accounting-firm` creates the store from the preset (its
  schema validated by `tiroir.core.schema`), grants Alice `write`, makes it her
  default store, and indexes it; `tiroir admin stores list` shows it.
- A `personal` store without `--owner`, or with a second grant, is refused.
- Through `core.member("alice")`: `stores()` lists the store with its access;
  `list_drawers()` lists the preset's clients; `append_log` on a client applies
  directly (personal store) and returns its commit; `search` finds the new
  entry within 2 s and every hit names its store (M3).
- Through `core.member("bob")` with no grant, every call naming that store
  raises `store.unknown`, exactly as for a store that does not exist.
- `tiroir admin index --rebuild` rebuilds the index and the same queries
  return the same hits.
- `tiroir.core` exposes the contract's names used above, and
  `lint-imports` still passes.
- `mise run check` passes.

## Validation

`mise run test -- tests/integration/test_api.py
tests/integration/test_presets.py tests/integration/test_admin_stores.py`, then `mise run check`.
