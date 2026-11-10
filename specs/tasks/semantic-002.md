---
id: semantic-002
title: Store chunk vectors in the index and embed new chunks in the background
type: feat
epic: semantic
depends_on: [semantic-001]
parallel: true
conflicts_with: [semantic-003, semantic-004, context-002, skill-001, eval-001]
tier: build
review: []
---

## Context

The index holds chunks, metadata, names and the FTS5 table, updated by the
background indexer after each commit (`search-001`). ADR-005 and ADR-009 add
vectors: one float32 BLOB per chunk and model, embedded after the text is
indexed so lexical search sees a write at once, and loaded into the server
process as NumPy arrays per store and model. The model loads in the
background at start. This task also takes the index work the skeleton review
deferred to the retrieval milestone.

## Covers

- R7

## Scope

Files this task is expected to touch:

- `src/tiroir/core/index.py`: a `vectors` table (`chunk_id`, `model_id`,
  `vector` BLOB) keyed by chunk and model, rows removed with their chunk; the
  model recorded in `meta`; read helpers returning the chunk ids still
  missing a vector for a model
- `src/tiroir/core/vectors.py`: the in-memory matrices per store and model
  (`numpy` arrays with their chunk ids), loaded on first use, updated when the
  indexer adds or removes vectors, never mixing models
- `src/tiroir/core/indexer.py`: after a store's text is indexed, embed its
  chunks missing a vector (passage side, in batches) with the store's model;
  a job is still dropped and logged on failure (the next one catches up)
- `src/tiroir/core/api.py`: `Core` loads the default model in a background
  thread at `open_core` (with `start_workers`), and exposes whether it is
  ready; `index(rebuild=True)` rebuilds vectors too; at `open_core`, refuse to
  start with `CoreError("index.no-fts5")` when the SQLite build lacks FTS5
  (ADR-005)
- The deferred `search-001` items:
  - a shared lock (a file lock under `<data>/locks/index-<store-id>`) taken
    by the indexer thread and by `tiroir admin index --rebuild`, so an older
    diff is never applied over a newer index;
  - a rebuild classifies a file by its path before reading its blob, so
    attachments and unknown files are never read
- `tests/integration/test_vectors.py`, `tests/integration/test_index.py`,
  `tests/integration/test_indexer.py`, using the test embedder of
  `semantic-001`; `tests/integration/test_sqlite_fts5.py`: the FTS5 check, run
  in CI by `mise run check`

Out of scope:

- searching the vectors, thresholds, fusion (`semantic-003`)
- a model per store, external services, switching models (`semantic-004`):
  here every store uses `DEFAULT_MODEL`
- the evaluation (`eval-001`)

## Acceptance criteria

- After `append_log` on a personal store, the entry is found by lexical
  search within 2 s as before, and its chunk has a vector once the indexer is
  idle; a test asserts both.
- Until the model has loaded, the indexer indexes text and leaves vectors
  missing; once it is ready, the missing vectors are filled without a new
  commit.
- Deleting `<data>/index/<store-id>.sqlite` and running `index(rebuild=True)`
  gives, for a fixed list of queries, the same lexical hits in the same order
  and byte-identical vectors per chunk (R7).
- A rebuild started while the indexer is applying a diff waits for the lock,
  and the index afterwards matches the head of `main`; a test runs both
  concurrently.
- A store holding a binary file the schema does not know is rebuilt without
  that blob being read (a test counts the blob reads).
- `open_core` on a Python whose SQLite lacks FTS5 raises `index.no-fts5`
  (tested by forcing the probe); the CI run includes the probe test.
- `mise run check` passes.

## Validation

`mise run test -- tests/integration/test_vectors.py
tests/integration/test_index.py tests/integration/test_indexer.py
tests/integration/test_sqlite_fts5.py`, then `mise run check`.
