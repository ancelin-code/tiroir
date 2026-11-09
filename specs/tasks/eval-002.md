---
id: eval-002
title: Write the judged query sets of both presets
type: feat
epic: eval
depends_on: [presets-001]
parallel: true
conflicts_with: []
tier: build
review: []
---

## Context

Each preset ships a judged query set including negative queries (V2). The
sets decide the default model (R4a), the default threshold, and the four
retrieval questions the milestone settles (`eval-003`), so they must test
what users ask: exact identifiers (R2), inflected and unaccented French (R3),
paraphrases sharing no word with the answer (what semantic search is for),
and questions the store cannot answer. They also hold detection cases with
negatives (C3). The data is the synthetic datasets of `accounting-firm`
(`store-003`) and `developer` (`presets-001`).

## Covers

- V2

## Scope

Files this task is expected to touch:

- `presets/accounting-firm/eval.yaml` and `presets/developer/eval.yaml`, in
  the format below (defined with `eval-001`, which loads it):

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

- Per set, at least: 60 positive queries, of which at least 10 exact
  identifiers or numbers (SIREN with and without spaces, invoice numbers,
  ticket numbers, versions), 10 surnames or proper nouns, 15 paraphrases
  sharing no content word with their answer, and, in the French set, 10
  unaccented or inflected forms; 20 negative queries, half of them close to
  the store's topics (a client or a subject that does not exist), including
  the skeleton review's `relance TVA` case written so that only one drawer is
  relevant; 30 detection cases, of which at least 10 negatives (ordinary
  text, common words, names that are not drawers), 3 ambiguous names and, in
  the developer set, 5 working-directory cases
- `presets/accounting-firm/README.md`, `presets/developer/README.md`: the
  set, how it was judged, and how to extend it
- `tests/integration/test_query_sets.py`: every relevant path exists in the
  preset's data, every section is one of its file's sections, every expected
  drawer exists, and the counts above hold (this test parses the YAML
  directly, so it does not wait for `eval-001`)

Out of scope:

- the loader and the metrics (`eval-001`)
- running the evaluation and drawing conclusions (`eval-003`)
- changing the presets' data, except to add a fact a query needs (each such
  change listed in the pull request)

## Acceptance criteria

- Both files exist with the counts above, and `test_query_sets.py` passes.
- Every relevant judgement was checked by reading the file it names; the
  README states how the sets were judged and by whom.
- No query is copied from a summary sentence word for word; paraphrase
  queries share no content word with their answer once normalised (the test
  checks it with `textnorm.terms`).
- `mise run check` passes.

## Validation

`mise run test -- tests/integration/test_query_sets.py`, then `mise run check`.
