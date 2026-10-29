---
id: docs-001
title: Publish the user documentation as a Zensical site on GitHub Pages
type: docs
epic: docs
depends_on: []
parallel: true
conflicts_with: []
tier: build
review: []
---

## Context

The 0.1.0 release works end to end, and its guides (`docs/install/vps.md`,
`docs/connect/claude-desktop.md`) sit as loose Markdown. Users need a site, and
every later milestone must update it. Delivery Kit's launch plan picked
Zensical on GitHub Pages with the `llms.txt` output; follow the same choice.
The requirements are in [the PRD](../prd.md).

## Scope

Files this task is expected to touch:

- `zensical.toml` (site configuration and navigation)
- `docs/index.md` (home page: what tiroir is, who it is for, where to start)
- `docs/install/vps.md` (the image is now published: pull it instead of
  building, in the start and upgrade steps; `TIROIR_TAG` takes `v0.1.0` style
  tags or `latest`)
- `docs/connect/claude-desktop.md` (only what the site needs, such as links)
- `docs/reference/cli.md` (user-facing CLI reference, written for users from
  `delivery/contracts/cli.md`, not copied from it)
- `.github/workflows/docs.yml` (build on pull requests, deploy to GitHub Pages
  from `develop`)
- `pyproject.toml`, `uv.lock` (Zensical as a pinned dev dependency, with its
  licence checked by `mise run licenses`)
- `mise.toml` (`docs:build` and `docs:serve` tasks)
- `README.md` (slim: pitch, quickstart, link to the site; fix the stale
  "design phase, nothing is usable yet" line)
- `AGENTS.md` (a short rule: a milestone is not delivered until the site
  documents what it adds; each task that changes user-visible behaviour
  updates its page)
- `delivery/tasks/docs-001.md`

Out of scope:

- ADRs, contracts, the brief, research notes and milestone notes stay in the
  repository and out of the site's navigation.
- A custom domain, search plugins beyond Zensical's defaults, a theme redesign.
- Documenting features that do not exist yet.

## Acceptance criteria

- `mise run docs:build` builds the site with no warning, and the output holds an
  `llms.txt`.
- The navigation holds exactly: Home, Install (VPS), Connect (Claude Desktop),
  Reference (CLI).
- `docs/install/vps.md` no longer says that no image is published, and starts
  and upgrades the stack with `docker compose pull` and `up -d`, with
  no `--build`; `compose.yaml` still builds locally for contributors.
- The CLI reference lists every command of the CLI contract with its arguments
  and an example, and matches the real `tiroir --help` output.
- The workflow builds on pull requests and deploys to GitHub Pages only on push
  to `develop`; Zensical is pinned to an exact version.
- The README links to the site and to nothing that moved without a working
  target.
- `AGENTS.md` states the per-milestone documentation rule.
- `mise run check` and `mise run licenses` pass.

## Validation

```sh
mise run docs:build
mise run check
mise run licenses
```
