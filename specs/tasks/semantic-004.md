---
id: semantic-004
title: Choose a store's embedding model or an external service, with a background re-index
type: feat
epic: semantic
depends_on: [semantic-002]
parallel: true
conflicts_with: [semantic-002, semantic-003, context-002, skill-001, eval-001, presets-002, context-004, eval-003, guides-001, skill-002, presets-001]
tier: build
review: [security]
---

## Context

Every store uses `DEFAULT_MODEL` after `semantic-002`. R4 and ADR-006 let the
administrator choose, per store, another local model from the registry or an
OpenAI-compatible external service, which sends the store's content out of
the server and is allowed only for stores the administrator explicitly
configured (network invariant). Changing a store's model re-embeds it in the
background while the old vectors and threshold stay in service. A store's
threshold comes from the registry, or from a calibration stored in
`server.db` (written by `eval-001`).

## Covers

- R4 (part): the per-store choice of a local model or an external service,
  the confirmation that content leaves the server, the background re-index on
  change and the per-model threshold; the administration page's statement
  comes with that page in the team milestone

## Scope

Files this task is expected to touch:

- `src/tiroir/core/migrations/0005_embeddings.sql` (or the next free number):
  a per-store embedding choice (local model id, or external base URL, model
  name and secret file name) and a per-store, per-model calibrated threshold
- `src/tiroir/core/serverdb.py`: read and write those rows
- `src/tiroir/core/api.py`: `AdminContext.set_embedding(store, choice)` (R4;
  starts the re-index), the store's active model and threshold resolved for
  search (calibrated, else the registry's, else none and `not-calibrated`); an
  external store without calibration searches lexically and says so
  (ADR-006)
- `src/tiroir/core/types.py`, `src/tiroir/core/__init__.py`:
  `EmbeddingChoice` (local model id, or external base URL, model name, key
  variable)
- `src/tiroir/core/indexer.py`: the switch: embed every chunk with the new
  model into new rows, keep searching with the old model and threshold until
  it is complete, then switch and drop the old rows
- `<data>/secrets/` handling: the API key read from the environment variable
  named by `--key-env` at configuration time and written to a file readable
  only by the server's user; never in `server.db`, logs or output
- `src/tiroir/cli/admin.py`: `tiroir admin embedding <store> [--model <id> |
  --external <base-url> --external-model <name> --key-env <VAR>]` per the
  [CLI contract](../contracts/cli.md); `--external` prints that the store's
  content will be sent to that service and asks for confirmation (`--yes`
  skips it); without options it prints the store's current choice and
  re-index state
- `tests/integration/test_embedding_choice.py` (a local HTTP server stands in
  for the external service), `tests/unit/cli/test_admin.py`
- `docs/install/embeddings.md` (new, added to the `nav` of `zensical.toml`):
  the default model, other local models, the external option and exactly what
  it sends and to whom, calibration; `docs/reference/cli.md`

Out of scope:

- the calibration run itself (`tiroir admin eval --calibrate`, `eval-001`)
- the administration page (team milestone)
- adapters for non-OpenAI-compatible vendor APIs (ADR-006)

## Acceptance criteria

- `tiroir admin embedding s --model multilingual-e5-small` records the choice
  and starts a re-index; until it completes, search keeps the old model's
  results and threshold; after it, the index holds only the new model's
  vectors (tests with two test embedders of different dimensions).
- `tiroir admin embedding s --external http://127.0.0.1:<port> --external-model
  m --key-env K` without `--yes` asks for confirmation naming the service;
  after confirmation, chunks are embedded through the test service, the key
  is read from `<data>/secrets/` with mode `0600`, and it appears in no log
  line, no `server.db` column and no command output.
- An external store without a calibrated threshold searches lexically and
  reports `not-calibrated`; with a threshold row, it searches both channels.
- The external service unreachable during search gives lexical results with
  `external-unavailable`, not an error.
- An unknown model id is refused with a message listing the registry's ids.
- `mise run docs:build` passes with the new page in the nav; `mise run check`
  passes.

## Validation

`mise run test -- tests/integration/test_embedding_choice.py
tests/unit/cli/test_admin.py`, `mise run docs:build`, then `mise run check`.
