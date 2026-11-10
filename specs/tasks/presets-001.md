---
id: presets-001
title: Write the developer preset with its synthetic dataset
type: feat
epic: presets
depends_on: []
parallel: true
conflicts_with: [semantic-003, semantic-004, context-004, skill-002, eval-001, eval-003, guides-001]
tier: build
review: []
---

## Context

Two presets ship (S4): `accounting-firm` (French, `store-003`) and
`developer` (English), which does not exist yet. It is the solo developer's
store in Claude Code: one drawer per repository, detected by name and by the
working directory (C1a). It also carries the English judged query set
(`eval-002`), so its data must give search and detection real work:
identifiers, version numbers, proper nouns, and plain-language questions
whose answer uses other words.

## Covers

- S4

## Scope

Files this task is expected to touch:

- `presets/developer/tiroir.yaml`: language `en`, audience `personal`; a
  `repo` drawer type at `repos/{slug}` with fields `slug` (text, required,
  pattern), `name` (text, required), `aliases` (list), `language` (enum of a
  few programming languages), `status` (enum `active`, `maintenance`,
  `archived`); summary sections such as `Purpose`, `Architecture`,
  `Conventions`, `Decisions`, `Gotchas`, `Open questions`; `detect.names:
  [slug, name, aliases]`, `detect.cwd: slug`; `inject.sections` a subset
  with `max_tokens`; `shared.topics` and `shared.conventions`
- `presets/developer/templates/`, `presets/developer/shared/` (conventions, a
  release checklist, a code review guide)
- `presets/developer/data/`: at least 20 repository drawers, each with
  `summary.md` and 5 to 25 log entries over 2025 and 2026, in the
  [store layout](../contracts/store-layout.md); the data includes ticket and
  issue numbers (`PROJ-1234`, `#482`), version numbers (`v2.14.3`), error
  codes, hostnames on `example.com`, invented library and people names, and
  at least two drawers whose names overlap (`api` and `api-gateway`) to
  exercise longest-match detection
- `presets/developer/README.md`: contents, and that all data is synthetic
- `docs/reference/presets.md` (new, added to the `nav` of `zensical.toml`):
  both bundled presets, their drawer types and shared documents, that their
  data is synthetic, and how a store is created from one
- `tests/integration/test_developer_preset.py`: the preset validates with
  `tiroir.core.schema`, a store is created from it, and the shape rules below
  hold

Out of scope:

- the judged query set (`eval-002`)
- the administrator's own presets folder (`presets-002`)

## Acceptance criteria

- `tiroir admin stores add dev --audience personal --language en --owner
  <handle> --preset developer` creates a store that indexes without error.
- At least 20 drawers; every summary has exactly the schema's sections in
  order and frontmatter matching the fields; every log entry has `date` and
  `author` frontmatter and a path matching its date.
- Every hostname, e-mail and URL uses `example.com` or `example.org`; no
  person, company or repository name is a real one, as far as a reasonable
  search shows; the README says so.
- Every drawer's `slug` is unique once slugified, so a working directory
  `/home/u/src/<slug>/pkg` can name exactly one drawer (C1a; the detection
  cases themselves are in `eval-002`'s set).
- `mise run docs:build` passes with the new page in the nav; `mise run check`
  passes.

## Validation

`mise run test -- tests/integration/test_developer_preset.py`, then
`mise run check`.
