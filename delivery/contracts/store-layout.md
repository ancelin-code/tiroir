# Contract: store layout and commit format

**Status:** draft
**Parties:** core (store reading and writing, index, sync, purge, migration),
presets and their synthetic datasets, evaluation datasets, anyone reading a
store without tiroir (S5).

## Purpose

Fixes the files a store contains and the shape of each, and the commit
format sync replays (ADR-003, ADR-010, ADR-011). Every writer produces exactly
these shapes; every reader accepts them.

## Shape

### Tree

```text
<store>/
  tiroir.yaml                 schema (contract schema.md)
  MEMORY.md                   derived entry document, regenerated, never merged
  templates/                  templates referenced by the schema
  shared/                     shared space: *.md, sub-folders allowed
  <drawer path>/              one per drawer, from the type's `path` pattern
    summary.md
    log/<yyyy>/<entry file>.md
  .tiroir/purges.yaml         purge records (created by the first purge)
```

No other top-level entries are written by tiroir. Files tiroir does not know
are left alone, not indexed, and reported by `doctor`.

### Slugs and identifiers

- **Slug:** NFKC, diacritics removed, lowercase, every run of characters
  outside `[a-z0-9]` replaced by `-`, leading and trailing `-` trimmed, at most
  64 characters. `Boulangerie Dupont & Fils` → `boulangerie-dupont-fils`.
- **Drawer id:** the drawer's folder path relative to the store root, for
  example `clients/c042`. A **drawer ref** across stores is
  `<store name>:<drawer id>`, for example `cabinet-exemple:clients/c042`.
- **Entry id:** the entry file's path relative to the store root.

### `summary.md`

```markdown
---
type: client
code: C042
name: Boulangerie Dupont
aliases: [Dupont, BD]
legal_form: SARL
---
# Boulangerie Dupont

## Identité
...

## Régime fiscal
...
```

- Frontmatter: YAML, `type` (the drawer type name), then the type's fields in
  schema order. Values follow the field types of `schema.md`. Absent optional
  fields are omitted. tiroir writes frontmatter in one canonical form
  (ADR-003): strings double-quoted when they need quoting, lists in flow
  style, dates unquoted.
- Body: an optional level-1 title, then exactly the declared level-2 sections
  in declared order. Text before the first section and level-3 headings inside
  sections are allowed. A section's content is everything up to the next
  level-2 heading.

### Log entry

Path: `<drawer path>/log/<yyyy>/<yyyy-mm-dd>T<hhmmss>Z-<author>-<rand>.md`,
UTC, `<author>` the author's handle, `<rand>` 4 characters of `[a-z0-9]`.

```markdown
---
date: 2026-10-21T14:32:05Z
author: alice
---
Relance envoyée pour les justificatifs de frais manquants.
```

Frontmatter fields `date` (ISO 8601 UTC) and `author` (handle) are required;
others are not allowed in v1. The body follows the type's log template. An
entry file is never modified after its commit (W1, Y10).

### Shared documents

Markdown under `shared/`. Optional frontmatter with `title`. Level-2 headings
are sections for merging and chunking. The conventions document is the one
named by `shared.conventions`.

### `MEMORY.md`

Generated: store name and description, layout explanation, then one line per
drawer, `- [[<drawer id>/summary]] — <label>: <names>`, grouped by type and
sorted by drawer id. Written in the store language. After a replay or merge it
is regenerated from the resulting tree, never merged.

### `.tiroir/purges.yaml`

```yaml
purges:
  - epoch: 1
    date: 2026-10-21T15:00:00Z
    author: alice
    path_digests: ["9f2c…"]
    blobs: ["3b18e512dba79e4c8300dd08aeb37f8e728b8dad"]
```

`path_digests` are `sha256(store.id + "/" + path)`, in hex.

Append-only; entries are never edited or removed.

### Commits

One commit per operation, on branch `main`, linear history.

```text
tiroir: log-append clients/c042

Tiroir-Op: log-append
Tiroir-Drawer: clients/c042
Tiroir-Author: alice
Tiroir-Machine: 6f1d0c2e
```

| Trailer | Required | Meaning |
|---|---|---|
| `Tiroir-Op` | yes | One of `store-init`, `log-append`, `summary-update`, `doc-update`, `doc-create`, `drawer-create`, `outside-edit`, `migration`, `purge`. |
| `Tiroir-Drawer` | when the operation targets a drawer | Drawer id. |
| `Tiroir-Author` | yes | Author handle (Y4f). |
| `Tiroir-Machine` | yes | First 8 hex characters of the machine id (data directory), to tell machines apart. |
| `Tiroir-Base` | for `summary-update`, `doc-update`, `outside-edit` | `<path>@<blob id>` of each changed file's base version, one trailer per file. |
| `Tiroir-Schema` | for `migration` | Format version and hash of the resulting schema. |

The subject line is `tiroir: <op> <drawer id or "shared" or "store">`. No
memory content (text, metadata values, names other than the drawer id) ever
appears in a commit message (Y5). Commit author and committer are the user's
display name with the address `<handle>@tiroir.invalid`.

## Example

A drawer creation followed by one log entry produces two commits: the first
adds `clients/c042/summary.md` and regenerates `MEMORY.md`
(`Tiroir-Op: drawer-create`); the second adds
`clients/c042/log/2026/2026-10-21T143205Z-alice-k3f9.md`
(`Tiroir-Op: log-append`).

## Error cases

| Condition | Result |
|---|---|
| Summary sections missing, extra or out of order | `summary.invalid-sections`; reported by `doctor`; a proposal touching it is refused until fixed by a proposal |
| Log entry with an unknown or missing frontmatter field, or modified after commit | `log.invalid` / `log.modified` (Y10); restoring the committed version is offered |
| Two drawers resolve to the same folder | `drawer.path-collision` at creation; nothing is written |
| Commit without the required trailers on the store branch | treated as an outside change: sync stops and reports (ADR-010) |

## Changing this contract

Lanes are building against this. A change needs agreement from every party
listed above, and the lanes must be told; a silent change produces work that
cannot be integrated. After release, any change to these shapes requires a
schema format bump and a migration.
