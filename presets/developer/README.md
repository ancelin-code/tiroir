# Preset `developer`

An English store for a solo developer working in Claude Code: one drawer per
repository, found by name or by the working directory, with the developer's
conventions, a release checklist and a code review guide as shared documents.

## Contents

- `tiroir.yaml`: the schema, with one `repo` drawer type.
- `templates/`: the templates of a repository summary and of a log entry.
- `shared/`: the conventions, a release checklist and a code review guide.
- `data/`: a synthetic dataset in the store layout, with 23 repository
  drawers. Each has a `summary.md` and 5 to 25 log entries between January
  2025 and October 2026. `api` and `api-gateway` overlap on purpose, to
  exercise longest-match detection.

## All data is synthetic

Everything under `data/` is invented. No person, company, library or
repository name belongs to a real one.

- People have made-up names; the log authors are the handles `maya`, `tomas`,
  `ines` and `kofi`.
- Company, product and library names (`Brambleworth`, `Quillfold`,
  `Marrowdb`) are invented.
- Every hostname and e-mail address uses the reserved domains `example.com`
  or `example.org`.
- Ticket numbers (`PROJ-1234`), issue numbers (`#482`), version numbers
  (`v2.14.3`) and error codes have no meaning.

The dataset exists to test search and detection: identifiers, version numbers,
proper nouns, and plain-language questions whose answer uses other words
(a "slow" page is described as a query run on every request).
`tests/integration/test_developer_preset.py` checks the shape of the dataset
and these properties.

The schema's `store.id` is a placeholder; a store created from this preset
gets its own.
