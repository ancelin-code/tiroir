---
id: store-001
title: Load and validate the store schema
type: feat
epic: store
depends_on: [foundation-001]
parallel: true
conflicts_with: []
tier: build
review: []
---

## Context

Every store is configured by `tiroir.yaml`, whose exact shape, defaults and
error codes are fixed by the [schema contract](../contracts/schema.md);
[ADR-003](../decisions/ADR-003-store-format.md) fixes the YAML rules (YAML 1.2
with `ruamel.yaml`, no anchors, aliases, tags or multiple documents, canonical
writing). Nothing reads a store before this exists.

## Covers

- S1
- S2
- S6 (part): a schema that does not validate yields `schema.invalid` with every
  violation; refusing writes on that basis is `store-002`'s

## Scope

Files this task is expected to touch:

- `src/tiroir/core/schema/` (a package, one module per concern): dataclasses for the schema, `load_schema(text:
  str) -> Schema` (raises `CoreError` code `schema.invalid` /
  `schema.unsupported-version` / `schema.invalid-path` /
  `schema.unknown-section` / `schema.invalid-detect`, listing every violation
  with key path and line), `dump_schema(schema) -> str` (canonical form),
  `validate_metadata(drawer_type, mapping) -> list[Violation]`
- `src/tiroir/core/yaml_io.py`: the shared safe YAML 1.2 reader and canonical
  writer (also used for frontmatter by `store-002`)
- `src/tiroir/core/errors.py`: `CoreError` with `code` and a message free of
  memory content
- `tests/unit/core/schema/` (`test_load.py`, `test_dump.py`, `test_metadata.py`), `tests/unit/core/test_yaml_io.py`,
  `tests/unit/core/schema/fixtures/` (valid and invalid schema files)

Out of scope:

- editing `src/tiroir/core/__init__.py` (only `server-003` exports the public
  API); tests import the sub-modules directly
- migrations (operations milestone), the init skill (team milestone)

## Acceptance criteria

- The contract's example schema loads, and `dump_schema(load_schema(x))`
  round-trips to the same canonical text.
- Each error case of the contract's table has a fixture and yields its code;
  a file with three independent errors reports all three, each with its key
  path and line.
- Anchors, aliases, tags and a second document are refused with
  `schema.invalid`; `no`, `on` and `yes` stay strings (YAML 1.2).
- `validate_metadata` accepts a valid client's frontmatter from the contract's
  example and reports every violation of an invalid one.
- `mise run check` passes.

## Validation

`mise run test -- tests/unit/core/schema tests/unit/core/test_yaml_io.py`, then
`mise run check`.
