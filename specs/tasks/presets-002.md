---
id: presets-002
title: Let the administrator add their own presets in one folder of the server
type: feat
epic: presets
depends_on: []
parallel: true
conflicts_with: [semantic-004, eval-001]
tier: build
review: []
---

## Context

`tiroir admin stores add --preset <name>` reads presets from the image's
`/app/presets` (`TIROIR_PRESETS`) only, so an administrator with their own
schema must copy the bundled presets out of the image or override the stack's
configuration (`docs/install/custom-schema.md`). S7 asks for one documented
folder on the server, kept across upgrades, whose presets are used by name
like bundled ones, validated the same way, and never silently replacing a
bundled one of the same name. The data volume (`/data`) already survives
upgrades (ADR-016).

## Covers

- S7

## Scope

Files this task is expected to touch:

- `src/tiroir/core/presets.py`: resolve a preset name in the bundled
  directory and in `<data>/presets/`; a name found in both is refused with
  `CoreError("preset.conflict")` naming the folder to rename, and nothing is
  created; a list of every available preset with its origin (`bundled` or
  `server`); an administrator's preset goes through `load_preset`, so it is
  validated exactly as a bundled one
- `src/tiroir/cli/admin.py`: `stores add --preset` uses that resolution;
  `stores presets` lists the available presets with their origin (an
  addition to the [CLI contract](../contracts/cli.md)'s `stores` group, to be
  recorded there through `etabli-spec`)
- `tests/integration/test_admin_presets.py`, `tests/unit/cli/test_admin.py`
- `docs/install/custom-schema.md`: rewritten around the folder
  (`/data/presets/<name>/` inside the container, the volume's path outside),
  the layout of a preset, validation, the name rule; `docs/reference/cli.md`

Out of scope:

- uploading presets from the administration page (team milestone)
- the init interview proposing a schema (team milestone, I1)
- excluding a preset's evaluation file from the store (`eval-001`)

## Acceptance criteria

- A preset folder copied to `<data>/presets/acme/` is used by `stores add
  acme-memory … --preset acme`, and the store's files are that preset's.
- A preset of the administrator's whose schema is invalid is refused with
  `schema.invalid` and the same location messages as a bundled one; nothing
  is created.
- A folder `<data>/presets/accounting-firm/` makes `--preset accounting-firm`
  fail with `preset.conflict`; the bundled preset is not replaced, and
  `stores presets` shows both origins.
- After the container image is replaced by a new build (the data volume
  kept), the administrator's preset is still listed and usable: checked in a
  test by recreating the core on the same data directory with a different
  bundled directory.
- `mise run docs:build` passes; `mise run check` passes.

## Validation

`mise run test -- tests/integration/test_admin_presets.py
tests/unit/cli/test_admin.py`, `mise run docs:build`, then `mise run check`.
