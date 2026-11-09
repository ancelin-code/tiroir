# ADR-003: Store a drawer as a summary file plus one file per log entry, configured by `tiroir.yaml`

**Status:** accepted
**Date:** 2026-10-21, revised 2026-10-22 for the server

## Context

Every component reads and writes the same files: the schema, summaries, log
entries and shared documents. Their shape decides whether concurrent writes
conflict (Y4a), whether summaries can be merged section by section (Y4b),
whether the store is usable without tiroir (S5, H3) and whether migrations can
rewrite the schema safely (I4). The exact shapes
are in the contracts `schema.md` and `store-layout.md`; this record fixes the
choices behind them.

## Decision

- **One syntax, YAML 1.2,** for every structured file in a store: the schema,
  the frontmatter, the purge records (ADR-011) and the drawer moves
  (ADR-014). Frontmatter has to be YAML, the format Obsidian and other
  Markdown tools read, so using it everywhere leaves readers one syntax.
  tiroir parses with `ruamel.yaml` in YAML 1.2 safe mode, refuses anchors,
  aliases, tags and multi-document files, and writes every file itself in one
  canonical form (fixed key order, explicit quoting), so its output is stable
  across versions.
- **Schema file:** `tiroir.yaml` at the store root. It holds the store's
  identity (id, name, audience, language) and the drawer types. Only tiroir
  writes it (init and migrations), in canonical form; explanations go in the
  schema's `description` fields, which are data.
- **Drawer:** a folder whose path comes from the drawer type's layout pattern
  (for example `clients/{code}`, slugified), holding:
  - `summary.md`: YAML frontmatter for the metadata fields, then a body whose
    level-2 headings are exactly the sections the schema declares, in order.
    A section is the unit of merge (Y4b) and of injection (C4).
  - `log/<yyyy>/<mm>/<timestamp>-<author>-<random>.md`: **one file per log entry**,
    with `date` and `author` in its frontmatter. Concurrent appends create
    different files and never conflict.
- **Shared space:** Markdown documents under `shared/`. Level-2 headings are
  their sections for merging. The conventions document is one of them, named
  in the schema.
- **Templates:** Markdown files under `templates/`, referenced by the schema.
- **Entry document:** `MEMORY.md` at the root, compatible with the Agent Memory
  Repo format: what the store is, its layout, and links to every drawer. It is
  **derived**: tiroir regenerates it after every change and never merges it.
- **tiroir's own state in the store:** `.tiroir/` (purge records, ADR-011;
  drawer moves, ADR-014). Nothing about the server, its members or their
  access is ever written to the store (ADR-004).
- **Identifiers:** a drawer's identifier is its folder path relative to the
  store root (`clients/c042`). Path segments are lowercase ASCII slugs, so
  they behave the same on case-insensitive file systems (macOS, Windows).

## Alternatives considered

- **One log file per drawer, appended to** - simplest to read, but every
  append rewrites a growing file, a purge of one entry rewrites the whole log,
  and a clone or mirror diff shows the whole file changing. Writes are
  serialised on the server (ADR-010), so conflicts are no longer the reason;
  immutability of each entry (W1) and single-entry purge (E3) are.
- **One log file per drawer per day or per author** - fewer files, but entries
  stop being immutable files, with the same purge cost.
- **Metadata in a separate YAML file** - cleaner for tools, but splits one
  record across two files a non-developer must keep in sync; frontmatter is
  what Obsidian and every other Markdown tool already understand.
- **TOML for the schema** - its editing libraries keep comments across
  rewrites. Rejected: the schema is written only by tiroir (init, presets,
  migrations), so there are no hand-written comments to keep, and two syntaxes
  in one store cost every reader. YAML's indentation errors are caught because
  unknown keys and wrong types are errors.
- **JSON Schema for metadata** - expressive, but far beyond the field types S2
  requires and unreadable for the init skill's audience.

## Consequences

A drawer with 2,000 log entries is 2,000 small files; Git and file systems
handle this, and year and month folders keep each directory to a few
hundred files, under the 1,000 entries Git hosts' web views list. Reading a
whole log means reading many files, which only the indexer and the "read
log" operation do. Section headings become structural: renaming a section is a
migration. People who open a clone or a mirror meet one syntax, YAML.
