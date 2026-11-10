---
id: eval-001
title: Evaluate retrieval and detection on a judged query set, and calibrate a store's threshold
type: feat
epic: eval
depends_on: [semantic-003, semantic-004, context-001, context-003]
parallel: true
conflicts_with: [semantic-002, semantic-003, semantic-004, context-002, context-003, context-004, skill-001, presets-002, guides-001, skill-002, presets-001, eval-003]
tier: plan
review: []
---

## Context

The abstention threshold depends on the model and is calibrated per store
and model, and the default model is chosen from the evaluation (R4a), which
is why evaluation is a Must (`prd.md`, Evaluation). V1 asks for recall@k, MRR
and the false-positive rate on negative queries for lexical-only,
semantic-only and hybrid retrieval, and for drawer detection; V4 lets members
run it on their own store with their own query set, and the administrator
calibrate a store's threshold from it (ADR-006). The retrieval settings are
selectable through `RetrievalSettings` (`semantic-003`), and detection is
`context-001`'s.

## Covers

- V1
- V4

## Scope

Files this task is expected to touch:

- `src/tiroir/core/queryset.py`: loading a judged query set, in this format
  (shared with `eval-002`, which writes the bundled sets):

  ```yaml
  queries:
    - id: q01
      query: "quand tombe la TVA de la boulangerie ?"
      drawers: [clients/c004]        # optional: the scope; absent = all_drawers
      relevant:                      # empty or absent: a negative query
        - clients/c004/summary.md#Échéances   # a path, optionally #section
        - clients/c004/log/2026/03/2026-03-03T163327Z-hugo-3w6h.md
  detection:
    - id: d01
      text: "Prépare la relance pour Boulangerie Dupont"
      cwd: null                      # optional
      drawers: [clients/c004]        # expected detections; empty: a negative
      ambiguous: []                  # expected ambiguous names, optional
  ```

  A relevant item matches a hit with that path, and that section when one is
  given. Errors name the query id and the key, never the query text (Y5).
- `src/tiroir/core/evaluation.py`: for each of lexical, vector and hybrid
  (and any `RetrievalSettings` given): recall@1, @5, @10, MRR, the
  false-positive rate on negative queries (a negative with any hit), the
  abstention rate on positives, and p50/p95 query time; for detection:
  precision, recall, false detections on negatives, ambiguities as expected;
  the calibration: the threshold is the smallest cosine, in steps of 0.01, at
  which no negative query admits a vector candidate, and the report shows
  recall@5 at that threshold (`eval-003` may revise the rule on evidence)
- `src/tiroir/core/api.py`: `MemberContext.evaluate(store, queries)` and
  `AdminContext.calibrate(store, queries)` (stores the threshold for the
  store's model in the table of `semantic-004`); `queries` is the query set's
  text, or `None` for the set of the preset the store came from. The [core
  API contract](../contracts/core-api.md) types it as a `Path`; a member's
  set arrives as text through MCP, so the contract is to be amended through
  `etabli-spec`
- `src/tiroir/core/types.py`, `src/tiroir/core/__init__.py`: `EvalReport`
- `src/tiroir/core/presets.py`: a preset's judged set lives at
  `presets/<name>/eval.yaml` and is not copied into the store
- `src/tiroir/core/migrations/` (the next free number) and
  `src/tiroir/core/serverdb.py`: the name of the preset a store was created
  from, recorded at creation, so `queries=None` finds that preset's set
- `src/tiroir/cli/admin.py`: `tiroir admin eval --store <s> [--queries
  <file>] [--calibrate] [--json]`, a table per channel on stdout
- `src/tiroir/server/mcp.py`: the `eval` action of `tiroir_store`
  (`options.queries`: the set's YAML text, optional), its report as Markdown
  and structured content, with no memory text in it
- `tests/unit/core/test_evaluation.py` (metrics on given hit lists),
  `tests/unit/core/test_queryset.py`, `tests/integration/test_evaluation.py`
  (a fixture store and a small fixture set, the test embedder),
  `tests/integration/test_mcp_tools.py`
- `docs/reference/cli.md`; `docs/reference/evaluation.md` (new, added to the
  `nav` of `zensical.toml`): the query set format, the metrics, calibration

Out of scope:

- the bundled judged sets (`eval-002`)
- the model comparison and the parameter decisions (`eval-003`)
- the member CLI's `tiroir eval` (member CLI, operations milestone)

## Acceptance criteria

- On a fixture store with a fixture set, `tiroir admin eval --store s`
  prints recall@5, MRR and negative false-positive rate for lexical, vector
  and hybrid, and detection precision, recall and false detections; `--json`
  gives the same as `EvalReport`'s serialisation.
- Metrics match hand-computed values on constructed hit lists (unit tests).
- `--calibrate` stores a threshold for the store's model; the next search
  uses it and no longer reports `not-calibrated`.
- A member with read access calls `tiroir_store {"action": "eval", "store":
  …, "options": {"queries": "<yaml>"}}` and gets the report; a member without
  a grant gets `store.unknown`.
- A query set with an unknown key or a malformed relevant item is refused
  with the query id and key in the message, and no query text.
- A store created from a preset does not contain `eval.yaml`.
- `mise run docs:build` passes; `mise run check` passes.

## Validation

`mise run test -- tests/unit/core/test_evaluation.py
tests/unit/core/test_queryset.py tests/integration/test_evaluation.py
tests/integration/test_mcp_tools.py`, `mise run docs:build`, then
`mise run check`.
