---
id: docs-002
title: Polish the documentation site and document custom schemas for administrators
type: docs
epic: docs
depends_on: []
parallel: true
conflicts_with: []
tier: build
review: []
---

## Context

The review of the published site ([docs-001](docs-001.md)) found it very good
and asked for five changes: a dark mode, a logo, two clearer navigation labels,
and an administrator page on defining a custom schema. In 0.1.0 a store is
always created from a preset (`preset.required`), and the only way to give it a
custom schema is a preset directory of the administrator's own, found through
`TIROIR_PRESETS`. The guided init skill that would write a schema from an
interview (I1, I2) is planned for the `team` milestone and does not exist yet;
the page must say so and not promise it. Requirements: [the PRD](../prd.md);
schema format: [the schema contract](../contracts/schema.md).

## Scope

Files this task is expected to touch:

- `zensical.toml` (colour palette with a light/dark toggle, the logo, the nav
  labels, the new page in `nav` and in the `llmstxt` sections)
- `docs/assets/` (the logo, an SVG of an old-fashioned wooden chest of drawers,
  usable on the light and dark palettes; also the favicon)
- `docs/install/custom-schema.md` (new: administrator guide to a custom schema)
- `docs/reference/cli.md`, `docs/install/vps.md`, `docs/index.md` (only the
  links, and the sentences that say a store can only start from the bundled
  preset)
- `delivery/tasks/docs-001.md` is left as it is: it records the first site.

Out of scope:

- Building the init skill, a `--schema` option or any code change. A mount for
  custom presets in `compose.yaml` is documented as an override file the
  administrator writes, not added to the shipped Compose file.
- A custom domain, a theme redesign beyond the palette and logo.

## Acceptance criteria

- The site offers a light and a dark mode, follows the visitor's system
  preference by default, and has a visible toggle.
- The site shows a logo in the header and as favicon: a wooden chest of drawers,
  legible on both modes.
- The navigation reads: Home; Server Installation (Installation Guide,
  Custom Schema); Client Installation (Connect Claude Desktop, where other
  hosts such as Claude Code will join later); CLI Reference. The page titles
  match their navigation labels, Home excepted.
- `docs/install/custom-schema.md` walks an administrator, from a clean 0.1.0
  install, through: copying the bundled preset as a starting point, editing
  `tiroir.yaml` (drawer types, fields, templates, sections, detection,
  injection) with a pointer to the field reference, making the directory
  available to the container and setting `TIROIR_PRESETS`, creating a store
  with `--preset <name>`, and checking the result. It states plainly that
  there is no guided init in 0.1.0 and that it is planned. Every command and
  path in it was run or read in the code, not guessed.
- No page says that `accounting-firm` is the only possible starting point
  without pointing to the new page.
- `mise run docs:build` succeeds with no warning, and `llms.txt` lists the new
  page.

## Validation

`mise run docs:build`, then open the built site (`mise run docs:serve`) in both
modes. Follow the new page's steps against a local store and confirm the store
is created from the custom preset.
