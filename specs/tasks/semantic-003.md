---
id: semantic-003
title: Search semantically and fuse lexical and vector ranks
type: feat
epic: semantic
depends_on: [semantic-002]
parallel: true
conflicts_with: [semantic-002, semantic-004, context-002, skill-001, eval-001, eval-003, context-004, skill-002, presets-001, guides-001]
tier: plan
review: []
---

## Context

Search is lexical only and reports `vectors-pending` (`search-001`,
`server-003`). With vectors in the index (`semantic-002`), ADR-007 fixes the
rest: up to 50 vector candidates after the scope and metadata filters, a
cosine floor per model, Reciprocal Rank Fusion with k = 60, an exact
identifier match first, the best vector candidate kept in the top 3, and rank
fusion across stores. The evaluation (`eval-001`, `eval-003`) compares
channels and fusion settings, so they must be selectable without code
changes.

## Covers

- R1
- R5

## Scope

Files this task is expected to touch:

- `src/tiroir/core/semantic.py`: `search_vector(stores, query, scope,
  filters, limit)`: embed the query (query side), filter the chunk ids by
  scope and filters **before** scoring (X1), brute-force dot product on the
  store's matrix, admit candidates at or above the model's threshold
- `src/tiroir/core/fusion.py`: fusion of admitted candidates: RRF with a
  given k, and a convex combination of min-max normalised scores with a given
  weight (the alternative `eval-003` compares); then ADR-007's two rules;
  across stores, ranks are fused, never cosines
- `src/tiroir/core/lexical.py`: return admitted candidates with their rank,
  and take the floor fraction (default one half) as a parameter
- `src/tiroir/core/retrieval.py`: a `RetrievalSettings` value (channels
  `lexical` / `vector` / `hybrid`, fusion method and its parameter, lexical
  floor fraction, candidate count), with defaults equal to ADR-007, used by
  search and by the evaluation
- `src/tiroir/core/api.py`: `MemberContext.search` runs both channels and
  fuses them; `degraded` says why a channel was skipped, using the contract's
  values accurately: `model-loading` while the model loads,
  `vectors-pending` only while some chunks in scope still lack a vector,
  `not-calibrated` when the store's model has no threshold (search is then
  lexical); a store whose model is unavailable (download failed) reports
  that, never "pending" (skeleton review)
- `src/tiroir/core/types.py`: only if a degraded value is missing from the
  contract; raise it to the contract owner rather than inventing one silently
- The deferred date-filter item of `search-001`: decide and document whether
  `since`/`until` keep undated summaries and shared documents (they do not
  today), and test the chosen rule
- `docs/use/search.md` (new, added to the `nav` of `zensical.toml`): what
  search finds (keywords, identifiers, meaning), scoping to drawers and the
  explicit cross-drawer search, what an abstention means, each degraded mode
  and what it says
- `tests/unit/core/test_fusion.py` (pure ranks), `tests/integration/test_semantic.py`,
  `tests/integration/test_hybrid.py`, with the test embedder of `semantic-001`

Out of scope:

- per-store model choice and calibrated thresholds stored in `server.db`
  (`semantic-004`, `eval-001`): here the threshold comes from the registry
- changing the defaults of ADR-007 (`eval-003` decides them on evidence)
- a reranker (ADR-007: none in v1)

## Acceptance criteria

- With the test embedder, a query sharing no word with a chunk but close to
  it in vector space is found by hybrid search with `channels` containing
  `vector` only; a query for an identifier ranks the identifier match first,
  `channels` containing `identifier`.
- A query whose best vector candidate ranks below 3 after fusion is moved to
  rank 3 at most (Cairn's guard), tested on constructed ranks.
- A query no channel admits returns `abstained` true and no hits, in hybrid,
  lexical-only and vector-only settings.
- The scope rule holds for vectors: with drawers `A` in scope, no hit comes
  from drawer `B` even when `B`'s chunk is the nearest vector (X1), and with
  no drawer in scope only shared-space chunks come back (M5).
- Search during model loading is lexical and reports `model-loading`; with a
  model and no threshold, it reports `not-calibrated`; with every chunk
  embedded, `degraded` is empty.
- Two stores searched together fuse by rank: a store whose cosines are all
  higher does not take every top place by itself (tested with two stores and
  scaled vectors).
- `RetrievalSettings` defaults equal ADR-007's values; a test reads them.
- `mise run docs:build` passes with the new page in the nav; `mise run check`
  passes.

## Validation

`mise run test -- tests/unit/core/test_fusion.py
tests/integration/test_semantic.py tests/integration/test_hybrid.py
tests/integration/test_lexical.py`, then `mise run check`.
