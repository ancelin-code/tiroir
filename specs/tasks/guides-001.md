---
id: guides-001
title: Bring the documentation site up to date with the retrieval milestone
type: docs
epic: guides
depends_on: [semantic-003, semantic-004, context-004, skill-002, presets-001, presets-002, eval-001, eval-003]
parallel: true
conflicts_with: [semantic-003, semantic-004, context-004, skill-002, presets-001, eval-001, eval-003]
tier: build
review: []
---

## Context

A milestone is not delivered until the site documents what it adds
(AGENTS.md). Each task of this cut documents its own user-visible change in
the same pull request: search (`semantic-003`), embedding models
(`semantic-004`), Claude Code (`context-004`), the memory skill
(`skill-002`), the presets (`presets-001`, `presets-002`), evaluation and
models (`eval-001`, `eval-003`). This task is the milestone's documentation
pass, run once they are merged: what no single task owns (the roadmap, the
changelog, the README, the per-host capability table), the Claude Desktop
guide the skeleton review found wrong, and a read of the whole site against
what the milestone now does. Every milestone's cut ends with such a task
(`specs/decomposition.md`, Milestones).

## Scope

Files this task is expected to touch:

- `docs/connect/claude-desktop.md`: the dialog as observed on 2026-10-27
  (Settings → Connectors → **+ Add** → "Add custom connector"; only **Name**
  and **Remote MCP server URL**; the **Continue** button; Claude's tool
  approvals and what to allow), then a link to the memory skill page
- `docs/connect/hosts.md` (new, added to the `nav` of `zensical.toml`): the
  per-host capability table (Claude Code with the plugin, Claude Desktop,
  web, mobile): automatic context, memory skill, tools; what works without
  hooks
- `docs/roadmap.md`: the Retrieval milestone delivered, Team next
- `CHANGELOG.md`, `docs/changelog.md`: an `[Unreleased]` section listing what
  the milestone adds, as the 0.1.0 entry does, ready to become the next
  version at tagging
- `README.md`: the status line
- any page of `docs/` that the milestone made inaccurate (for example a
  mention of keyword search only, or of `vectors-pending`); each fix listed in
  the pull request

Out of scope:

- the pages each task owns, except to fix an inaccuracy found in the read
- the exit check (`guides-002`)
- documentation for the team milestone (confirmations, team stores)

## Acceptance criteria

- `docs/connect/claude-desktop.md` matches the dialog observed in the
  skeleton review, step by step; the project owner checks it against Claude
  Desktop once more and the pull request says on which version.
- Every item of the changelog's `[Unreleased]` section links to, or is
  described on, a page of the site; the pull request lists each item with its
  page.
- The pull request records that every page in the `nav` was read, and lists
  what was corrected.
- No page asks a member to use a terminal or a Git command (U4, Y1).
- `mise run docs:build` passes (strict), and
  `tests/integration/test_docs_links.py` passes.

## Validation

`mise run docs:build`, `mise run test -- tests/integration/test_docs_links.py`,
then `mise run check`.
