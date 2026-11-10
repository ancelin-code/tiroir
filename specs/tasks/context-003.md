---
id: context-003
title: Serve tiroir_context and the memory skill's tool on the MCP endpoint
type: feat
epic: context
depends_on: [context-002, skill-001]
parallel: true
conflicts_with: [eval-001]
tier: build
review: [security]
---

## Context

The MCP endpoint serves `tiroir_search`, `tiroir_read`, `tiroir_write` (`log`)
and `tiroir_status` (`server-004`). The [MCP tools contract](../contracts/mcp-tools.md)
adds `tiroir_context`, which the Claude Code hook calls on every prompt, and
`tiroir_store`, whose `skill` action tells the member where to get their
memory skill (`skill-001`). This task adds both, renders the context block of
the [hook contract](../contracts/claude-code-hook.md), and keeps every tool
definition together under the token budget.

The hook contract names `tiroir.adapters.claude_code` as the renderer of the
context block, but `tiroir.server` may not import an adapter (the
independence contract of `pyproject.toml`, ADR-013), and every host gets the
same block from the tool. The block is therefore rendered in
`tiroir.server`; the contract's wording is to be corrected through
`etabli-spec`.

## Covers

- C4 (part): every injected line quoted under the reference-data sentence,
  and store identifiers kept outside the quoted block in every tool result
  (the deferred `server-004` item)
- C5
- C5b

## Scope

Files this task is expected to touch:

- `src/tiroir/server/context_block.py`: rendering a `ContextResult` as the
  hook contract's Markdown block, in its order, each part omitted when empty,
  every memory line prefixed by `> `; store names, drawer refs and audiences
  in headings outside the quotes
- `src/tiroir/server/mcp.py`:
  - `tiroir_context(text, cwd, session_id)`: under 3 characters, an empty
    text at once; otherwise `MemberContext.context` with a 1.2 s deadline,
    `session_id` defaulting to the MCP session's id; never a tool error for a
    detection problem (empty text instead); structured content from `to_json`
  - `tiroir_store` with the `skill` action only for now (the address of the
    member's skill archive on `/account/skill.zip`), other actions answering
    `params.invalid`; `eval` is added by `eval-001`
  - `tiroir_status`: whether the member's memory skill is out of date
    (`skill-001`)
  - the C4 item deferred by `server-004`: in `tiroir_search`, `tiroir_read`
    and the drawer list, drawer ids, types, paths and authors move out of the
    quoted reference-data block, and only memory text stays inside it
- `tests/integration/test_mcp_context.py`, `tests/integration/test_mcp_tools.py`
- `tests/unit/server/test_context_block.py`

Out of scope:

- the Claude Code plugin and its hook declaration (`context-004`)
- `tiroir_store` actions other than `skill` and `eval`, `tiroir_confirm`
  (later milestones)
- the latency benchmark (`bench-001`)

## Acceptance criteria

- Through the MCP client of the integration tests, `tiroir_context` with the
  hook contract's example prompt returns the block of the contract's example:
  heading, trust sentence, conventions on the first call of the session, one
  `### Client Boulangerie Dupont — <store>:clients/<id> (<audience>)` block
  with quoted sections; a second call in the same session has no conventions
  part.
- A prompt naming nothing, a 2-character prompt, and a forced core error each
  return an empty text and no tool error.
- An ambiguous name gives the `### Ambiguous` part listing the candidate refs
  and the advice to ask the user.
- `tiroir_store {"action": "skill"}` returns the address of the member's
  archive; `tiroir_status` reports the skill as out of date after the
  member's grants change.
- No result of `tiroir_search`, `tiroir_read` or `tiroir_context` puts a
  drawer ref, a path or a store name inside a quoted line, checked on every
  tool by one test.
- The six tools' definitions together stay under 2,000 tokens (U1, C5), by
  the documented approximation of `server-004`'s test.
- `mise run check` passes.

## Validation

`mise run test -- tests/integration/test_mcp_context.py
tests/integration/test_mcp_tools.py tests/unit/server/test_context_block.py`,
then `mise run check`.
