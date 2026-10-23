---
id: store-003
title: Write the accounting-firm preset with its synthetic dataset
type: feat
epic: store
depends_on: [foundation-001]
parallel: true
conflicts_with: []
tier: build
review: []
---

## Context

The skeleton's store is created from the `accounting-firm` preset (S4): a
French schema, templates, conventions and a synthetic dataset. The schema
contract's example is the starting point. The data must look real enough to
test search (identifiers, numbers, surnames, accents, inflected forms) and be
entirely invented: no real person or company.

## Covers

- S4 (part): the `accounting-firm` preset with its schema, templates,
  conventions and at least 20 synthetic drawers with summaries and logs; the
  `developer` preset and both judged query sets come in the retrieval
  milestone

## Scope

Files this task is expected to touch:

- `presets/accounting-firm/tiroir.yaml`: the schema contract's example (one
  `client` drawer type), in French, with `description` fields on the type and
  its fields
- `presets/accounting-firm/templates/client-summary.md`,
  `presets/accounting-firm/templates/client-log.md`
- `presets/accounting-firm/shared/conventions.md` and two or three shared
  documents (a fiscal calendar, a reminder-letter procedure)
- `presets/accounting-firm/data/`: the synthetic dataset as store files in the
  layout of the [store layout contract](../contracts/store-layout.md): at
  least 20 client drawers, each with `summary.md` and 5 to 30 log entries
  spread over 2025 and 2026, under `log/<yyyy>/<mm>/`
- `presets/accounting-firm/README.md`: what the preset contains and the
  statement that all data is synthetic
- `tests/integration/test_accounting_firm.py`

Out of scope:

- loading the preset into a store (`server-003`)
- the judged query set (retrieval milestone)
- the `developer` preset (retrieval milestone)

## Acceptance criteria

- The preset's `tiroir.yaml` parses as YAML 1.2 and has every required key
  of the schema contract; its full validation by `tiroir.core.schema` is
  checked when `server-003` creates a store from it.
- At least 20 drawers; every summary has exactly the schema's sections in
  order and frontmatter matching the fields; every log entry has `date` and
  `author` frontmatter and a path matching its date.
- The data contains, for later search tests: SIREN numbers (9 digits, some
  written with spaces), invoice numbers like `2026-001`, surnames with
  accents, and the same notion written with different inflections
  (`déclaration`, `déclarations`, `échéance`).
- No name, SIREN, address or e-mail belongs to a real person or company:
  names are invented, SIREN numbers fail the Luhn check or come from a
  documented fictitious range, addresses use invented streets, e-mails use
  `example.fr`; the README says so.
- `mise run check` passes.

## Validation

`mise run test -- tests/integration/test_accounting_firm.py`, then `mise run check`.
