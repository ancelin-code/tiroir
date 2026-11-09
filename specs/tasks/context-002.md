---
id: context-002
title: Assemble the context of a request within its deadline
type: feat
epic: context
depends_on: [context-001]
parallel: true
conflicts_with: [semantic-002, semantic-003, semantic-004, skill-001, eval-001]
tier: build
review: [security]
---

## Context

`MemberContext.context(text, cwd, deadline)` is the one core call behind the
Claude Code hook and the `tiroir_context` tool
([core API](../contracts/core-api.md), [hook contract](../contracts/claude-code-hook.md)).
It detects drawers across the member's granted stores (`context-001`), and
returns the injection-policy sections of each detected drawer's summary
within the size cap, the store's conventions the first time the store is used
in the session, and the ambiguities. It never embeds, never runs past its
deadline and never raises.

## Covers

- C4 (part): each block holds the summary's `inject.sections` within
  `inject.max_tokens`, cut as `schema.md` says; the framing as reference data
  is rendered by the MCP tool (`context-003`)
- C5a
- C6 (part): the core call returns an empty result on any error or at the
  deadline; the hook's own failure handling is `context-004`'s

## Scope

Files this task is expected to touch:

- `src/tiroir/core/context.py`: building the `ContextResult`:
  - detection over the dictionaries of the member's granted stores only
    (X1a: a store not granted contributes no name, not even to an ambiguity)
  - for each detection, a `ContextBlock` with the drawer's type label, its
    names, the store's audience and the `inject.sections` of its summary at
    `main`'s head, capped at `inject.max_tokens` (whole sections in declared
    order, then the last one cut), tokens counted with one documented
    approximation shared with `context-003`
  - conventions: the document named by `shared.conventions`, capped at
    `context.conventions_max_tokens`, returned for a store only the first
    time it appears in a result for that `session_id` (C5a); the record of
    which stores a session has seen is held in memory by the `Core`, bounded
    and expiring after 24 hours idle
  - a time budget checked between steps; at the deadline, or on any
    exception, an empty `ContextResult`, and the error code (no content, Y5)
    logged
- `src/tiroir/core/api.py`: `MemberContext.context`
- `src/tiroir/core/types.py`, `src/tiroir/core/__init__.py`: `DetectedVia`,
  `Detection`, `Ambiguity`, `Conventions`, `ContextBlock`, `ContextResult`
  as in the core API contract
- `tests/integration/test_context.py`

Out of scope:

- the MCP tool and the rendering of the context block (`context-003`)
- the Claude Code plugin (`context-004`)
- the deadline's value (1.2 s, set by the caller)

## Acceptance criteria

- The core API contract's example holds on the preset:
  `context("Prépare la relance TVA pour Boulangerie Dupont", None, 1.2)`
  detects the drawer and returns one block whose sections are the schema's
  `inject.sections` in order.
- A summary longer than the cap gives a block within `inject.max_tokens`,
  holding whole sections first and a cut last one.
- The conventions come back in the first result of a session that uses the
  store, and not in the second; a new `session_id` gets them again; without a
  `session_id`, they come back every time.
- A member granted store A only gets no detection, no ambiguity and no
  conventions from store B, even when B declares the same name as A (X1a).
- A deadline of 0 returns an empty result; an exception forced inside
  detection returns an empty result and logs only an error code.
- `context` makes no embedding call (a test embedder that fails when called
  is installed).
- `mise run check` passes.

## Validation

`mise run test -- tests/integration/test_context.py`, then `mise run check`.
