# ADR-012: Route every confirmed change through a local proposal, confirmed by MCP elicitation when the host supports it

**Status:** proposed
**Date:** 2026-10-21

## Context

Many operations need explicit user confirmation: summary updates (W2), every
write to a team store (W5), confirming outside edits (Y9), re-based changes
(Y4b), migrations (I3–I5) and purges (E1). The agent sits between tiroir and
the user, so "the agent says the user agreed" is weak. MCP elicitation lets a
server ask the user directly through the host's interface: Claude Code
supports it (since 2.1.76); Claude Desktop support is not confirmed as of
2026-10-21.

## Decision

- **One mechanism, the proposal.** An operation that needs confirmation first
  creates a proposal and changes nothing in the store. A proposal holds: an id,
  its kind (`log-append`, `summary-update`, `doc-update`, `drawer-create`,
  `outside-edit`, `migration`, `purge`), the target store with its name and
  audience, the target paths, the base version (blob id) of each changed file,
  the new content, a unified diff and a creation time.
- **Storage:** proposals live in the data directory, never in the store, and
  expire after 24 hours. Pending proposals are listed by the status tool and
  `tiroir proposals`.
- **Confirmation channel:**
  - if the MCP client declared the elicitation capability, the server asks
    the user directly with the diff, the store and its audience, and applies
    or discards the proposal from the answer; the tool call returns the
    outcome;
  - otherwise the tool returns the proposal, and the agent must show the diff
    to the user and call `tiroir_confirm` only after an explicit yes. The
    confirm tool is annotated as destructive so hosts ask before running it,
    and the documentation advises never to allow it permanently;
  - the CLI confirms interactively (`tiroir proposals confirm <id>`).
- **Applying:** the proposal is applied only if every changed file still has
  its base version. If not, a change limited to sections other than those
  changed in the meantime is combined into a new proposal; otherwise the
  proposal is marked `stale` and its intent is handed back to the agent to
  redo against the latest version (Y4b). Merging is per level-2 section.
- **No proposal** for a log append to a `personal` store (W5): it is written
  directly.

## Alternatives considered

- **Confirmation by a parameter on the write tool (`confirmed: true`)** - one
  call instead of two, but the agent can set it without asking anyone.
- **Elicitation only** - the strongest guarantee, but leaves Claude Desktop
  without any way to confirm while its support is unconfirmed.
- **Proposals stored in the store (a pending branch)** - shareable for review,
  but publishes unconfirmed content to everyone with access, which W5 forbids.

## Consequences

Where elicitation is unavailable, confirmation is only as strong as the
agent's honesty and the host's tool-permission prompt; the isolation and
erasure documentation says so. Proposals are per machine: a change proposed on
one laptop cannot be confirmed from another. Expiry means a forgotten proposal
disappears; the content of an unconfirmed outside edit stays in the working
copy, so nothing the user typed is lost.
