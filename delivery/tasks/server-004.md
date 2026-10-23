---
id: server-004
title: Serve the MCP endpoint with search, read and log tools
type: feat
epic: server
depends_on: [server-002, server-003]
parallel: true
conflicts_with: [server-001, server-002]
tier: build
review: [security]
---

## Context

Members reach tiroir through the streamable HTTP MCP endpoint at `/mcp`,
authenticated by the OAuth tokens of `server-002`, each call made as the
token's member through the core facade of `server-003`. Tool names,
parameters, results and errors are fixed by the
[MCP tools contract](../contracts/mcp-tools.md); the route and its `401`
behaviour by the [HTTP routes contract](../contracts/http-routes.md). The
skeleton needs the tools that let a member list drawers, read, append to a
log and search.

## Covers

- U1 (part): the `/mcp` endpoint with `tiroir_search`, `tiroir_read`
  (`drawers`, `summary`, `log`, `entry`), `tiroir_write` (`log` only) and
  `tiroir_status`, working as a remote connector after sign-in; the other
  tools and actions come in later milestones
- M3 (part): every hit and write outcome names its store; injected context
  and confirmations come later
- W1

## Scope

Files this task is expected to touch:

- `src/tiroir/server/mcp.py`: the MCP server (`mcp` SDK, streamable HTTP),
  server name `tiroir`, one-sentence instructions, the four tools above with
  their contract parameters, Markdown text with memory quoted as reference
  data (C4's framing) plus `structuredContent` from `to_json`, core errors as
  tool errors with their codes
- `src/tiroir/server/app.py`: mount `/mcp` behind the bearer-token check of
  `server-002`'s `verify.py`, answering `401` with the `WWW-Authenticate`
  header of the contract
- `tests/integration/test_mcp_tools.py`, `tests/integration/test_mcp_auth.py`,
  `tests/integration/test_end_to_end.py`

Out of scope:

- `tiroir_context`, `tiroir_confirm`, `tiroir_store`, `tiroir_write` actions
  other than `log`, `tiroir_read` `links` (later milestones)
- elicitation (team milestone)
- the Claude Code plugin (retrieval milestone)

## Acceptance criteria

- `tests/integration/test_end_to_end.py` starts the application on a temporary data
  directory with a store created from the preset, runs the OAuth flow as a
  client, opens an MCP session with the SDK's client, lists tools (exactly the
  four above), lists drawers, appends a log entry to a client, and finds it
  with `tiroir_search` within 2 s; the hit names the store, drawer, path,
  kind, date and author.
- A request to `/mcp` without a token, with an invalid one or one of a
  disabled member gets `401` with `WWW-Authenticate: Bearer
  resource_metadata="…/.well-known/oauth-protected-resource"`.
- A member without a grant on the store gets `store.unknown` from every tool,
  the same text as for a store that does not exist.
- The tool definitions together stay under 2,000 tokens, measured in a test
  with a documented approximation (characters / 4).
- `mise run check` passes.

## Validation

`mise run test -- tests/integration/test_mcp_tools.py
tests/integration/test_mcp_auth.py tests/integration/test_end_to_end.py`, then `mise run check`.
