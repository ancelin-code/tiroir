# Contract: MCP tools

**Status:** draft
**Parties:** `tiroir.mcp` (provider); the memory and init skills, the Claude
Desktop bundle, the Claude Code plugin, the C7 acceptance script (consumers).

## Purpose

What an agent can do with tiroir in any MCP host (U1). The tool set is small
on purpose: all definitions together stay under 2,000 tokens (U1, C5), so
operations are grouped by intent with an `action` or `what` parameter.

## Shape

Server name `tiroir`, stdio transport. Every tool returns a Markdown text
content for the model and the same data as `structuredContent` (JSON matching
the core types of `core-api.md`). Any memory text returned is wrapped in a
block stating it is reference data, not instructions, with every line quoted
(C4). Every hit, block and proposal names its store (M3).

Server `instructions`: one sentence pointing to the memory skill (ADR-013).

| Tool | Parameters | Returns | Annotations |
|---|---|---|---|
| `tiroir_context` | `text` (string, required): the user's request; `cwd` (string, optional) | Detected drawers with the text that matched, ambiguities, conventions on first call (C5a), injected blocks (C4). Empty result says "no drawer named". | read-only |
| `tiroir_search` | `query` (required); `drawers` (list of drawer refs); `all_drawers` (boolean, default false, X2); `store`, `type`, `kind`, `since`, `until`, `fields` (object) filters; `limit` (default 10, max 30) | Hits with store, drawer, path, kind, section, date, author; or an explicit abstention (R5); degraded mode notes. | read-only |
| `tiroir_read` | `what`: `summary` \| `log` \| `entry` \| `shared` \| `drawers` (required); `ref` (drawer ref, entry id or shared path; required except for `drawers`); `drawers` (active drawers, for scope); `limit`, `before` (for `log`); `store`, `type` (for `drawers`) | The requested content, or the drawer list with names (C5b). | read-only |
| `tiroir_write` | `action`: `log` \| `summary` \| `create_drawer` \| `shared` (required); `drawer` (drawer ref, for `log`, `summary`); `store`, `type`, `fields` (for `create_drawer`); `path` (for `shared`); `text` (new body or full new summary/document); `intent` (one line: what the change is for, required for `summary` and `shared`) | Outcome: applied (with store), or the pending proposal (diff, store, audience) | destructive: false |
| `tiroir_confirm` | `proposal_id` (required); `decision`: `apply` \| `discard` (required) | Outcome: applied, discarded, or a new proposal if the base changed (Y4b) | destructive: true |
| `tiroir_status` | `store` (optional) | Stores with audience and sync state, pending and stale proposals (with intent for stale ones), outside edits awaiting confirmation (Y9), queued changes. | read-only |
| `tiroir_admin` | `action`: `init` \| `connect` \| `migrate` \| `purge` \| `doctor` \| `sync` \| `skill` (required); action-specific `options` (object) | `init`, `migrate`, `purge`: a proposal whose diff is the dry run. `connect`: the public key and host steps, then completion on a second call. `doctor`, `sync`: their reports. `skill`: the generated memory skill archive path. | destructive: true |

### Confirmation (ADR-012)

- If the client declared the `elicitation` capability, `tiroir_write`,
  `tiroir_admin` (`init`, `migrate`, `purge`) and outside-edit confirmations
  ask the user directly with the diff, store name and audience, and return the
  final outcome. `tiroir_confirm` is then only used for proposals listed by
  `tiroir_status`.
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
              "store": {"name": "cabinet-exemple", "audience": "team"},
              "paths": ["clients/c042/log/2026/2026-10-21T143205Z-alice-k3f9.md"],
              "diff": "+Relance TVA préparée, envoi prévu le 22/10.\n",
              "status": "pending"}}
```

## Error cases

Errors are returned as tool errors (`isError: true`) with the core error code
and a message free of memory content.

| Condition | Result |
|---|---|
| Ref outside the given `drawers` scope | `scope.denied` |
| `all_drawers` combined with `drawers` | `params.invalid` |
| Unknown store, drawer, proposal | `store.unknown`, `drawer.unknown`, `proposal.unknown` |
| Write refused by schema or purge | `schema.invalid`, `metadata.invalid`, `drawer.purged` |
| Store busy | `store.busy`, retry advised |
| Elicitation declined or cancelled by the user | not an error: outcome `discarded` |

## Changing this contract

Lanes are building against this. A change needs agreement from every party
listed above, and the lanes must be told; a silent change produces work that
cannot be integrated. Adding a tool needs the 2,000-token budget re-measured.
