---
id: store-002
title: Create, read and write stores as bare Git repositories
type: feat
epic: store
depends_on: [store-001]
parallel: true
conflicts_with: []
tier: plan
review: []
---

## Context

A store is a bare Git repository on the server, with no working copy, written
by tiroir alone, one commit per operation under a per-store file lock
([ADR-010](../decisions/ADR-010-git-on-the-server.md),
[ADR-009](../decisions/ADR-009-server-process-model.md) for the lock). File
shapes, paths, slugs, `MEMORY.md` and the commit format are fixed by the
[store layout contract](../contracts/store-layout.md). Several constraints
interact here (compare-and-swap on the head, trailers, lock, schema refusal),
hence the `plan` tier.

## Covers

- W1
- Y2
- Y1 (part): tiroir creates, reads and commits to repositories with no Git
  action by anyone; mirrors and clones come in the operations milestone
- Y5 (part): commit messages carry operation, drawer id and handle only; the
  server's logs are `server-001`'s
- S6 (part): writes to a store whose schema does not validate are refused
  with `schema.invalid`

## Scope

Files this task is expected to touch:

- `src/tiroir/core/store.py`: `create_store(data_dir, store_id, files:
  Mapping[str, bytes], author) -> str` (the `store-init` commit from a set of
  files, such as a preset), `StoreReader` (head commit, read a file at a
  commit, list files, changed paths between two commits), `StoreWriter` (one
  operation: build the new tree from the head, write the commit, move `main`
  with compare-and-swap), `append_log(store, drawer_id, body, member) ->
  commit id`, `create_drawer_files(...)` used by store creation
- `src/tiroir/core/layout.py`: slugs, drawer paths from the type's pattern,
  log entry file names, frontmatter writing in canonical form, `MEMORY.md`
  generation
- `src/tiroir/core/locks.py`: the per-store `fcntl` lock at
  `<data>/locks/<store-id>`, with a 10 s timeout raising `store.busy`
- `tests/unit/core/test_layout.py` (slugs, paths, canonical frontmatter: pure
  logic), `tests/integration/test_store.py`, `tests/integration/test_locks.py`

Out of scope:

- editing `src/tiroir/core/__init__.py` (`server-003`)
- proposals and confirmation (team milestone): in this milestone every store
  is `personal`, where log appends apply directly
- summary updates, shared documents, drawer creation by members, links,
  purge, mirrors, clones
- the index (`search-001`), which reads stores through `StoreReader`

## Acceptance criteria

- `create_store` produces a bare repository at
  `<data>/stores/<store-id>.git` with one commit on `main` whose message and
  trailers match the contract (`Tiroir-Op: store-init`, `Tiroir-Via`,
  `Tiroir-Author`), and `MEMORY.md` generated from the drawers.
- `append_log` adds exactly one file at
  `<drawer>/log/<yyyy>/<mm>/<yyyy-mm-dd>T<hhmmss>Z-<author>-<rand>.md`, in one
  new commit whose parent is the previous head, with author and committer
  `<display name> <handle@tiroir.invalid>`; no memory text appears in the
  commit message.
- Two threads and two processes appending to the same store concurrently
  (a test with 20 appends each) end with every entry present, a linear
  history and no lost update.
- A store whose `tiroir.yaml` is invalid refuses `append_log` with
  `schema.invalid` and its repository is unchanged.
- A write whose lock is held for more than 10 s fails with `store.busy`.
- `mise run check` passes.

## Validation

`mise run test -- tests/unit/core/test_layout.py
tests/integration/test_store.py tests/integration/test_locks.py`, then
`mise run check`.
