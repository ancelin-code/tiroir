# Presets

A preset is a folder with a schema, templates, shared documents and, usually,
a dataset. Tiroir bundles two. Every store starts from one: pass its name to
`--preset` when you create the store.

```text
$ tiroir admin stores add dev --audience personal --language en \
    --owner alice --preset developer
store: dev
```

The store gets its own identifier; the preset's is a placeholder. See
[`stores add`](cli.md#stores-add) for the options and
[Schema Reference](schema.md) for the schema keys.

!!! note "All bundled data is synthetic"
    Every person, company, repository, address and e-mail in the datasets is
    invented. E-mail addresses and hostnames use reserved domains
    (`example.fr`, `example.com`, `example.org`). Delete the drawers before
    you put real memory in a store created from a preset.

## `accounting-firm`

French, for an accounting firm. One drawer type.

| Drawer type | Path | Fields | Summary sections |
|---|---|---|---|
| `client` | `clients/{code}` | `code` (required, `C042`), `name` (required), `aliases`, `legal_form`, `fiscal_year_end` | Identité, Régime fiscal, Missions, Contacts, Points d'attention, Échéances |

Shared documents: the firm's conventions, a fiscal calendar and the
reminder-letter procedure. The dataset has 23 client drawers.

## `developer`

English, for a solo developer in Claude Code. One drawer per repository,
matched by name or by the working directory.

| Drawer type | Path | Fields | Summary sections |
|---|---|---|---|
| `repo` | `repos/{slug}` | `slug` (required), `name` (required), `aliases`, `language`, `status` | Purpose, Architecture, Conventions, Decisions, Gotchas, Open questions |

Shared documents: the developer conventions, a release checklist and a code
review guide. The dataset has 23 repository drawers with tickets (`PROJ-1234`),
issues (`#482`), versions (`v2.14.3`) and error codes. Two drawers, `api` and
`api-gateway`, have overlapping names.

## Your own presets

A preset of your own is a folder with the same layout; see
[Custom Schema](../install/custom-schema.md).
