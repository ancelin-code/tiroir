---
id: context-004
title: Ship the Claude Code plugin with its prompt hook
type: feat
epic: context
depends_on: [context-003]
parallel: true
conflicts_with: [semantic-004, eval-001, eval-003, guides-001, semantic-003, skill-002, presets-001]
tier: plan
review: [security]
---

## Context

A developer connects Claude Code to their server by installing one plugin
(U2, [ADR-013](../decisions/ADR-013-adapters-and-skills.md)). Its manifest
asks once for the server's address, declares the tiroir MCP server (Claude
Code runs the OAuth sign-in on first use) and a `UserPromptSubmit` hook of
type `mcp_tool` calling `tiroir_context` (`context-003`), as the
[hook contract](../contracts/claude-code-hook.md) fixes. ADR-013 says the
milestone must verify that the supported Claude Code version honours
`mcp_tool` hooks and plugin `userConfig`. The plugin is declarative files, not
Python, published from a marketplace hosted by this repository.

## Covers

- U2
- C6
- D1 (part): continuous integration checks the plugin on Linux, macOS and
  Windows; the server's checks on macOS and Windows hosts stay with the
  operations milestone

## Scope

Files this task is expected to touch:

- `.claude-plugin/marketplace.json`: the marketplace, listing the `tiroir`
  plugin from `plugins/claude-code`
- `plugins/claude-code/.claude-plugin/plugin.json`: name `tiroir`, version
  matching the package, `userConfig.server_url` (string, required, title
  "tiroir server address"), the MCP server `tiroir` of type `http` at
  `${user_config.server_url}/mcp`
- `plugins/claude-code/hooks/hooks.json`: the hook declaration of the
  contract, timeout 2 s
- `plugins/claude-code/README.md`
- `tests/unit/plugin/test_manifest.py`: the manifest, the hook and the
  marketplace parse, carry the contract's values, and agree with each other
  and with the tool name and parameters served by `tiroir.server.mcp`
  (reading the files under `plugins/`, no network)
- `.github/workflows/ci.yml`: a job running the plugin tests on
  `ubuntu-latest`, `macos-latest` and `windows-latest`, and validating the
  plugin with Claude Code's own validator when the CLI can be installed in CI
- `docs/connect/claude-code.md` (new, added to the `nav` of
  `zensical.toml`): installing the plugin in one command, the address prompt,
  the sign-in, what the hook injects and when, how to turn it off
- `docs/milestones/retrieval-claude-code-check.md`: the manual check below,
  with the Claude Code version it was run on

Out of scope:

- the init skill shipped with the plugin (team milestone, I1)
- the memory skill, which a Claude Code member uploads like any host
  (`skill-002`, `guides-001`)
- a hook for any other host

## Acceptance criteria

- `claude plugin marketplace add <repo>` then `claude plugin install
  tiroir@tiroir` installs the plugin and asks for the server address once;
  this is run by hand against a test server and recorded in
  `retrieval-claude-code-check.md` with the Claude Code version.
- In that session, after sign-in, a prompt naming a client of a store
  created from `accounting-firm` adds the context block to the model's
  context (shown by asking the model to quote it), and a prompt naming
  nothing adds nothing.
- With the server stopped, and with the member's token revoked, a prompt is
  answered normally without context; Claude Code at most reports a
  non-blocking hook error. Recorded in the same file.
- `tests/unit/plugin/test_manifest.py` passes on the three operating systems
  in CI.
- `mise run docs:build` passes with the new page in the nav; `mise run check`
  passes.

## Validation

`mise run test -- tests/unit/plugin`, the CI run on the three systems, the
manual check recorded in `docs/milestones/retrieval-claude-code-check.md`,
`mise run docs:build`, then `mise run check`.
