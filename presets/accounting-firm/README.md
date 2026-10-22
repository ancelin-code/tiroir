# Preset `accounting-firm`

A French store for an accounting firm: one drawer per client, with the
firm's conventions and procedures as shared documents.

## Contents

- `tiroir.yaml`: the schema, with one `client` drawer type.
- `templates/`: the templates of a client summary and of a client log entry.
- `shared/`: the conventions, a fiscal calendar and the reminder-letter
  procedure.
- `data/`: a synthetic dataset in the store layout, with 23 client drawers.
  Each has a `summary.md` and 6 to 24 log entries between January 2025 and
  October 2026.

## All data is synthetic

Everything under `data/` is invented. No person, company, address or e-mail
belongs to a real one.

- Names of people and companies are made up.
- Street names are invented; towns and postal codes are real only to look
  plausible.
- E-mail addresses use the reserved domain `example.fr`.
- SIREN numbers are random 9-digit numbers that **fail the Luhn check**, so
  none can be a registered SIREN. Some are written with spaces
  (`123 456 789`), the rest without.
- Invoice numbers (`2026-001`) are sequential counters with no meaning.

The dataset exists to test search: identifiers, numbers, accented surnames
and inflected forms (`déclaration`, `déclarations`, `échéance`, `échéances`).
`tests/presets/test_accounting_firm.py` checks the shape of the dataset and
these properties.

The schema's `store.id` is a placeholder; a store created from this preset
gets its own.
