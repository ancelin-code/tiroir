# Contract: MCP tools

**Status:** agreed
**Parties:** `tiroir.server` (provider, on the MCP Python SDK); the memory and
init skills, the Claude Code plugin and its prompt hook
(`claude-code-hook.md`), the member CLI, the C7 acceptance script
(consumers).

## Purpose

What an agent, or the member CLI, can do with tiroir from any MCP host (U1).
The tool set is small on purpose: all definitions together stay under 2,000
tokens (U1, C5), so operations are grouped by intent with an `action` or
`what` parameter. Server administration is not here: it lives on the
administration page and CLI (A3, ADR-013).

## Shape

**Endpoint:** streamable HTTP at `https://<server>/mcp` (contract
`http-routes.md`). Every request carries a bearer token obtained through the
OAuth flow, or a personal access token with the `cli` scope (ADR-015); a
request without a valid token gets HTTP 401 with the `WWW-Authenticate` header
pointing to the Protected Resource Metadata. The token's member is the caller
of every core function (`core-api.md`).

Server name `tiroir`. Every tool returns a Markdown text content for the model
and the same data as `structuredContent` (the JSON serialisation of the core
types). Any memory text returned is wrapped in a block stating it is reference
data, not instructions, with every line quoted (C4). Every hit, block and
proposal names its store (M3).

Server `instructions`: one sentence pointing to the memory skill (ADR-013).

| Tool | Parameters | Returns | Annotations |
|---|---|---|---|
| `tiroir_context` | `text` (string, required): the user's request; `cwd` (string, optional); `session_id` (string, optional, defaults to the MCP session) | The context block of `claude-code-hook.md` as text (empty text when nothing is detected); detections, ambiguities, conventions on first use per store and session (C5a) and injected blocks (C4) as structured content. | read-only |
| `tiroir_search` | `query` (required); `drawers` (list of drawer refs); `all_drawers` (boolean, default false, X2); `store`, `type`, `kind`, `since`, `until`, `fields` (object) filters; `limit` (default 10, max 30) | Hits with store, drawer, path, kind, section, date, author; or an explicit abstention (R5); degraded modes noted. | read-only |
| `tiroir_read` | `what`: `summary` \| `log` \| `entry` \| `shared` \| `drawers` \| `links` (required); `ref` (drawer ref, entry id or shared path; required except for `drawers`); `drawers` (active drawers, for scope); `all_drawers` (for `links`, X2); `limit`, `before` (for `log`); `store`, `type` (for `drawers`) | The requested content, the drawer list with names (C5b), or the outgoing and incoming links of `ref` with kind and matched text, filtered by scope (L4). | read-only |
| `tiroir_write` | `action`: `log` \| `summary` \| `create_drawer` \| `shared` (required); `drawer` (drawer ref, for `log`, `summary`); `store`, `type`, `fields` (for `create_drawer`); `path` (for `shared`); `text` (new body or full new summary/document); `intent` (one line: what the change is for, required for `summary` and `shared`) | Outcome: applied (with store), or the pending proposal (diff, store, audience). | destructive: false |
| `tiroir_confirm` | `proposal_id` (required); `decision`: `apply` \| `discard` (required) | Outcome: applied, discarded, or a new proposal if the base changed (Y4b). | destructive: true |
| `tiroir_status` | none | The member's stores with audience and access, pending and stale proposals (with intent for stale ones), whether the memory skill is out of date, degraded modes. | read-only |
| `tiroir_store` | `action`: `init` \| `migrate` \| `purge` \| `doctor` \| `eval` \| `skill` (required); `store`; action-specific `options` (object) | `init`, `migrate`, `purge`: a proposal whose diff is the dry run. `doctor`, `eval`: their reports. `skill`: the address of the member's memory skill archive on their account page. | destructive: true |

### Confirmation (ADR-012)

- If the client declared the `elicitation` capability, `tiroir_write` and
  `tiroir_store` (`init`, `migrate`, `purge`) ask the user directly with the
  diff, store name and audience, and return the final outcome.
  `tiroir_confirm` is then only used for proposals listed by `tiroir_status`.
- Otherwise they return the pending proposal with this instruction in the
  text: show the diff and the audience to the user, and call `tiroir_confirm`
  only after the user explicitly agrees.

## Example

```json
{"tool": "tiroir_write",
 "arguments": {"action": "log", "drawer": "cabinet-exemple:clients/c042",
               "text": "Relance TVA préparée, envoi prévu le 22/10."}}
```

Result without elicitation, team store:

```json
{"applied": false,
 "proposal": {"id": "p-7k2d", "kind": "log-append",
              "store": {"name": "cabinet-exemple", "audience": "team", "access": "write"},
              "paths": ["clients/c042/log/2026/10/2026-10-21T143205Z-alice-k3f9.md"],
              "diff": "+Relance TVA préparée, envoi prévu le 22/10.\n",
              "status": "pending"}}
```

## Error cases

Errors are returned as tool errors (`isError: true`) with the core error code
and a message free of memory content. Authentication failures are HTTP 401
before any tool runs.

| Condition | Result |
|---|---|
| Ref outside the given `drawers` scope | `scope.denied` |
| `all_drawers` combined with `drawers` | `params.invalid` |
| Unknown or not granted store; unknown drawer, proposal | `store.unknown`, `drawer.unknown`, `proposal.unknown` |
| Write to a read-only store | `access.read-only` |
| Write refused by schema, purge or link check | `schema.invalid`, `metadata.invalid`, `drawer.purged`, `link.unresolved` |
| Store busy (migration or purge running) | `store.busy`, retry advised |
| Token revoked or member disabled during a session | HTTP 401 on the next request |
| Elicitation declined or cancelled by the user | not an error: outcome `discarded` |
| `tiroir_context` failure or deadline | not an error: empty result (C6) |

## Changing this contract

Lanes are building against this. A change needs agreement from every party
listed above, and the lanes must be told; a silent change produces work that
cannot be integrated.
