# Contract: store schema (`tiroir.toml`)

**Status:** draft
**Parties:** core (schema loading and validation, store, index, detection,
context, migration), init skill, presets, CLI `doctor`, memory-skill generator.

## Purpose

The one configuration file of a store (S1–S3, ADR-003). It declares the
store's identity and every drawer type: layout, metadata, templates, summary
sections, detection and injection. Everything that organises memory is here,
so no organisation is ever code (invariant).

## Shape

TOML 1.0, UTF-8, at the store root, read and rewritten with `toml_edit` so
comments and layout survive migrations (ADR-003). Unknown keys are errors, so
a typo never silently disables a rule. Paths are relative to the store root
and use `/`. Field locations below use dotted keys (`store.name` is `name` in
the `[store]` table).

### Top level

| Field | Type | Required | Meaning |
|---|---|---|---|
| `tiroir` | integer | yes | Format version of this file. `1` for v1. |
| `store.id` | string (UUID) | yes | Generated at creation, never changed. Keys all machine-side data (ADR-004). |
| `store.name` | slug | yes | Short name shown in results and confirmations (M3), for example `acme`. |
| `store.audience` | `personal` \| `team` | yes | Who reads the store (M2). `team` makes every write need confirmation (W5). |
| `store.language` | language code | yes | Memory language, ISO 639-1 (`en`, `fr`). Drives templates' language, the agent's writing language, stop words and stemming (S3, ADR-007). |
| `store.description` | string | no | One line on what the store holds; used in `MEMORY.md` and the memory skill. |
| `shared.path` | path | no | Folder of the shared space. Default `shared`. |
| `shared.topics` | list of string | no | Topics of the shared space, used in the memory skill's description (C5c). |
| `shared.conventions` | path | no | Shared document loaded on first use in a session (C5a). Default `shared/conventions.md` when it exists. |
| `context.conventions_max_tokens` | integer | no | Cap on the conventions block (C5a). Default 1500. |
| `drawer_types` | table of name → drawer type | yes | At least one, as `[drawer_types.<name>]` tables. Names are slugs (`client`, `repo`). |

### Drawer type

| Field | Type | Required | Meaning |
|---|---|---|---|
| `label` | string | yes | Human name in the memory language (`Client`, `Dépôt`). |
| `label_plural` | string | no | Plural, for the skill description and `MEMORY.md`. |
| `path` | pattern | yes | Folder of each drawer, with `{field}` placeholders replaced by the slug of that field's value: `clients/{code}`. Must contain at least one placeholder of a required field, and patterns of two types must not overlap. |
| `fields` | table of name → field (inline tables) | yes | Metadata fields, stored in the summary's frontmatter. Names are slugs; `type`, `author`, `date` are reserved. |
| `summary.template` | path | yes | Markdown template of a new summary (see below). |
| `summary.sections` | list of string | yes | Level-2 section headings, in order. At least one. The units of merge (Y4b) and injection (C4). |
| `log.template` | path | no | Markdown body template of a new log entry. Default: empty body. |
| `detect.names` | list of field names | no | Fields whose values name a drawer in text (C1, ADR-008). Fields must be `text` or `list`. |
| `detect.cwd` | field name | no | Field compared to the working directory's repository folder name or `origin` URL (C1a). |
| `inject.sections` | list of string | no | Sections injected when a drawer is detected (C4). Default: all. Each must be in `summary.sections`. |
| `inject.max_tokens` | integer | no | Cap on one drawer's injected block. Default 800. Truncation keeps whole sections in declared order, then cuts the last one. |

### Field

| Field | Type | Required | Meaning |
|---|---|---|---|
| `type` | `text` \| `number` \| `date` \| `boolean` \| `enum` \| `list` | yes | `date` is ISO 8601 `YYYY-MM-DD`; `list` is a list of text (S2). |
| `required` | boolean | no | Default `false`. |
| `values` | list of string | for `enum` | Allowed values. |
| `pattern` | regular expression | no | For `text` only; full match. |
| `default` | value of the field's type | no | Used by `drawer-create` and by migrations adding the field. |
| `description` | string | no | Shown by the init skill and in validation messages. |

### Templates

A summary template is Markdown containing exactly the level-2 headings of
`summary.sections`, in order, with optional guidance text under each. It may
use `{field}` placeholders, replaced at drawer creation. Frontmatter is
generated from the fields and is not part of the template.

## Example

```toml
tiroir = 1

[store]
id = "4b7e2c1a-9d3f-4e8b-a1c2-5f6d7e8f9a0b"
name = "cabinet-exemple"
audience = "team"
language = "fr"
description = "Mémoire du cabinet, un tiroir par client."

[shared]
topics = ["procédures", "modèles de lettres", "calendrier fiscal"]

[drawer_types.client]
label = "Client"
label_plural = "Clients"
path = "clients/{code}"

[drawer_types.client.fields]
code = { type = "text", required = true, pattern = "C[0-9]{3}" }
name = { type = "text", required = true }
aliases = { type = "list" }
legal_form = { type = "enum", values = ["EI", "SARL", "SAS", "SCI", "Association"] }
fiscal_year_end = { type = "date" }

[drawer_types.client.summary]
template = "templates/client-summary.md"
sections = ["Identité", "Régime fiscal", "Missions", "Contacts", "Points d'attention", "Échéances"]

[drawer_types.client.log]
template = "templates/client-log.md"

[drawer_types.client.detect]
names = ["code", "name", "aliases"]

[drawer_types.client.inject]
sections = ["Identité", "Points d'attention", "Échéances"]
max_tokens = 800
```

## Error cases

Validation (`doctor`, and before every write, S6) reports every violation, not
only the first, each with file, location and expected value.

| Condition | Result |
|---|---|
| Unknown key, wrong type, missing required key, TOML syntax error | `schema.invalid` with the key path and line, e.g. `drawer_types.client.fields.code.type` (line 18) |
| `tiroir` greater than the running version supports | `schema.unsupported-version`; nothing is read or written |
| Path pattern without a required-field placeholder, or overlapping another type | `schema.invalid-path` |
| `inject.sections` or template heading not in `summary.sections` | `schema.unknown-section` |
| Field listed in `detect` of a type other than `text` or `list` | `schema.invalid-detect` |
| A drawer's frontmatter violates its fields | `metadata.invalid` with drawer path, field and expected type; reported by `doctor`, blocks writes to that drawer only |

## Changing this contract

Lanes are building against this. A change needs agreement from every party
listed above, and the lanes must be told; a silent change produces work that
cannot be integrated. Any change to the file format after release bumps
`tiroir` and ships a migration.
