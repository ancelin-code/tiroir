---
id: search-001
title: Index stores and search them by keyword
type: feat
epic: search
depends_on: [store-002]
parallel: true
conflicts_with: []
tier: build
review: []
---

## Context

Each store has a derived SQLite index beside its repository, built from the
commits of `main` ([ADR-005](../decisions/ADR-005-index.md)). This task builds
its lexical half: chunks, French normalisation, identifier tokens, FTS5 and
the lexical abstention floor, as fixed by
[ADR-007](../decisions/ADR-007-retrieval.md). Vectors, fusion and the
evaluation come in the retrieval milestone; the index schema should leave room
for them without being built for them.

## Covers

- R1 (part): lexical retrieval with filters on drawer type, drawer, metadata
  fields, entry kind and date range; semantic retrieval and fusion are left to
  the retrieval milestone
- R2 (part): exact identifiers, numbers and surnames rank first on the
  synthetic data; the judged evaluation set comes later
- R3
- R6
- R7 (part): the index is derived and a rebuild gives identical results; the
  administration command is wired by `server-003`
- W4 (part): a commit is indexed within 2 s by the indexer, so the next search
  sees it; embeddings come later

## Scope

Files this task is expected to touch:

- `src/tiroir/core/index.py`: the per-store SQLite index at
  `<data>/index/<store-id>.sqlite` (WAL): files, chunks, metadata, names
  tables, an FTS5 table with a `text` column (normalised and stemmed) and an
  `ids` column (identifier tokens); `index_store(store) -> IndexReport`
  (incremental from the recorded commit to the head), `rebuild(store)`
- `src/tiroir/core/chunking.py`: chunks per summary section, per log entry
  (split at paragraphs above 400 tokens), per shared-document section
- `src/tiroir/core/textnorm.py`: NFKC, case folding, diacritics removal, stop
  words and Snowball stemming per language (`PyStemmer`), identifier tokens
- `src/tiroir/core/lexical.py`: `search_lexical(stores, query, scope, filters,
  limit) -> list[Hit]` with BM25 ranking, the lexical admission floor of
  ADR-007 and exact-identifier matches ranked first; an empty admitted set is
  an abstention
- `src/tiroir/core/indexer.py`: the background indexer of ADR-009 (a thread
  with a queue of store ids, fed after each commit and at start)
- `tests/unit/core/test_textnorm.py`, `tests/unit/core/test_chunking.py` (pure
  logic), `tests/integration/test_index.py`, `tests/integration/test_lexical.py`,
  `tests/integration/test_indexer.py` (real SQLite and Git)

Out of scope:

- editing `src/tiroir/core/__init__.py` (`server-003`)
- vectors, embeddings, fusion, calibration (retrieval milestone)
- links and mentions tables (operations milestone)
- the per-member access check, which the facade applies before calling this
  (`server-003`)

## Acceptance criteria

- On a store created from a fixture copy of the preset (or a small fixture
  store if `store-003` is not merged yet), `echeance` finds a chunk containing
  `échéance`, and `déclarations` finds `déclaration`.
- A SIREN written `123 456 789` in an entry is found by the query `123456789`
  and ranked first; an invoice number `2026-001` is found and ranked first.
- A query sharing no content term with the store returns an abstention, not
  the closest chunk.
- Filters by drawer type, drawer, field value, kind and date range each narrow
  the results as expected; with an empty scope and `all_drawers` false, only
  shared-space chunks are returned (M5's rule).
- After `append_log`, the indexer makes the new entry searchable in under 2 s
  in a test that measures it.
- Deleting the index file and rebuilding yields the same hits, in the same
  order, for a fixed list of queries.
- `mise run check` passes.

## Validation

`mise run test -- tests/unit/core/test_textnorm.py
tests/unit/core/test_chunking.py tests/integration/test_index.py
tests/integration/test_lexical.py tests/integration/test_indexer.py`, then
`mise run check`.
