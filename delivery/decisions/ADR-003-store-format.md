# ADR-003: Store a drawer as a summary file plus one file per log entry, configured by `tiroir.toml`

**Status:** proposed
**Date:** 2026-10-21

## Context

Every component reads and writes the same files: the schema, summaries, log
entries and shared documents. Their shape decides whether concurrent writes
conflict (Y4a), whether summaries can be merged section by section (Y4b),
whether the store is usable without tiroir (S5, H3) and whether migrations can
rewrite the schema without losing the user's comments (I4). The exact shapes
are in the contracts `schema.md` and `store-layout.md`; this record fixes the
choices behind them.

## Decision

- **Schema file:** `tiroir.toml` at the store root, TOML 1.0. It holds the
  store's identity (id, name, audience, language) and the drawer types. Read
  and rewritten with `toml_edit`, so migrations keep the user's comments,
  order and formatting.
- **Frontmatter:** YAML, the format Obsidian and other Markdown tools read.
  tiroir parses it with a YAML 1.2 parser and writes it itself in one
  canonical form (fixed key order, explicit quoting), so its output is stable
  across machines and versions.
- **Drawer:** a folder whose path comes from the drawer type's layout pattern
  (for example `clients/{code}`, slugified), holding:
  - `summary.md`: YAML frontmatter for the metadata fields, then a body whose
    level-2 headings are exactly the sections the schema declares, in order.
    A section is the unit of merge (Y4b) and of injection (C4).
  - `log/<yyyy>/<timestamp>-<author>-<random>.md`: **one file per log entry**,
    with `date` and `author` in its frontmatter. Concurrent appends create
    different files and never conflict.
- **Shared space:** Markdown documents under `shared/`. Level-2 headings are
  their sections for merging. The conventions document is one of them, named
  in the schema.
- **Templates:** Markdown files under `templates/`, referenced by the schema.
- **Entry document:** `MEMORY.md` at the root, compatible with the Agent Memory
  Repo format: what the store is, its layout, and links to every drawer. It is
  **derived**: tiroir regenerates it after every change and never merges it.
- **tiroir's own state in the store:** `.tiroir/` (purge records, ADR-011).
  Nothing machine-specific is ever written to the store.
- **Identifiers:** a drawer's identifier is its folder path relative to the
  store root (`clients/c042`). Path segments are lowercase ASCII slugs, so
  they behave the same on case-insensitive file systems (macOS, Windows).

## Alternatives considered

- **One log file per drawer, appended to** - simplest to read, but two
  machines appending concurrently edit the same file. A union merge driver
  interleaves multi-line entries and is not available without Git's own merge
  machinery.
- **One log file per drawer per day or per author** - fewer files, but still
  conflicts within a day or across an author's machines.
- **Metadata in a separate YAML file** - cleaner for tools, but splits one
  record across two files a non-developer must keep in sync; frontmatter is
  what Obsidian and every other Markdown tool already understand.
- **YAML for the schema** - one syntax with the frontmatter and lighter for
  nested structures, but the Rust ecosystem has no maintained YAML editor that
  preserves comments, so every migration would erase the user's notes in the
  file; YAML's indentation rules also produce silent errors for
  non-developers editing it, which TOML's explicit tables avoid.
- **JSON Schema for metadata** - expressive, but far beyond the field types S2
  requires and unreadable for the init skill's audience.

## Consequences

A drawer with 2,000 log entries is 2,000 small files; Git and file systems
handle this, and year folders keep directories short. Reading a whole log
means reading many files, which only the indexer and the "read log" operation
do. Editing a log by hand means editing one entry file, which Y10 then
rejects. Section headings become structural: renaming a section is a migration.
Users who open the files meet two syntaxes, TOML for the schema and YAML for
frontmatter; the init skill and migrations mean a non-developer edits neither
by hand.
