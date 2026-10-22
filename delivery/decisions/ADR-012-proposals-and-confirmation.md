# ADR-012: Route every confirmed change through a proposal held by the server for its member, confirmed by MCP elicitation when the host supports it

**Status:** proposed
**Date:** 2026-10-22

## Context

Many operations need explicit user confirmation: summary updates (W2), every
write to a team store (W5), re-based changes (Y4b), migrations (I3–I5) and
purges (E1). The agent sits between tiroir and the user, so "the agent says the
user agreed" is weak. MCP elicitation lets a server ask the user directly
through the host's interface: Claude Code supports it; support in Claude
Desktop, on the web and on mobile for remote connectors is to be checked in the
first milestone. Proposals now live on a server shared by several members.

## Decision

- **One mechanism, the proposal.** An operation that needs confirmation first
  creates a proposal and changes nothing in the store. A proposal holds: an id,
  the member who made it, its kind (`log-append`, `summary-update`,
  `doc-update`, `doc-create`, `drawer-create`, `migration`, `purge`,
  `store-init`), the target store with its name and audience, the target
  paths, the base version (blob id) of each changed file, the new content, a
  unified diff, an intent line and a creation time.
- **Storage:** in `server.db` (ADR-004), never in the store. A proposal belongs
  to its member: only they list, confirm or discard it; another member,
  administrators included, never sees it (X1a). Proposals expire after 24
  hours. A member's pending proposals are listed by `tiroir_status` and the
  CLI.
- **Confirmation channel:**
  - if the MCP client declared the elicitation capability, the server asks
    the user directly with the diff, the store and its audience, and applies
    or discards the proposal from the answer; the tool call returns the
    outcome;
  - otherwise the tool returns the proposal, and the agent must show the diff
    to the user and call `tiroir_confirm` only after an explicit yes. The
    confirm tool is annotated as destructive so hosts ask before running it,
    and the documentation advises never to allow it permanently;
  - the CLI confirms interactively.
- **Applying:** under the store's write lock, the proposal is applied only if
  every changed file still has its base version. If not, a change limited to
  sections other than those changed in the meantime is combined into a new
  proposal; otherwise the proposal is marked `stale` and its intent is handed
  back to the agent to redo against the latest version (Y4b). Merging is per
  level-2 section.
- **No proposal** for a log append to a `personal` store (W5): it is written
  directly. A member with read-only access gets `access.read-only` before any
  proposal is made (W6).

## Alternatives considered

- **Confirmation by a parameter on the write tool (`confirmed: true`)** - one
  call instead of two, but the agent can set it without asking anyone.
- **Elicitation only** - the strongest guarantee, but leaves hosts without
  elicitation unable to confirm anything.
- **Proposals visible to every member of the store** - would allow review by a
  colleague, but shows unconfirmed content to people the author has not chosen
  to share it with yet, which W5 forbids.
- **Confirmation on a tiroir web page** - independent of the host, but takes
  the user out of the conversation for every write, and A3 keeps memory
  content off the web pages.

## Consequences

Where elicitation is unavailable, confirmation is only as strong as the
agent's honesty and the host's tool-permission prompt; the isolation and
erasure documentation says so. Because proposals are on the server, a change
proposed in Claude Desktop can be confirmed from Claude Code or the CLI by the
same member. Expiry means a forgotten proposal disappears; it never reached the
store.
