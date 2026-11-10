---
id: guides-002
title: Write the retrieval exit check with its scripted conversations, and run it
type: test
epic: guides
depends_on: [eval-003, context-004, guides-001]
parallel: true
conflicts_with: []
tier: plan
review: []
---

## Context

The milestone's exit is checked on the skeleton's server: the evaluation
report on both sets, the default model within the budget, Claude Code
injecting a client's summary within 300 ms at p95, and, in Claude Desktop,
the memory skill making the agent use tiroir on a scripted set (C7) and
record new facts (W7). C7 and W7 are measured on scripted prompts and
conversations, run by a person in Claude Desktop, so the scripts and the
checklist are written before the run, as `deploy-002` did for the skeleton.
The skeleton review also left two questions to observe: whether Claude
Desktop declares the elicitation capability, and whether a token refresh
happens after the access token expires.

## Covers

- C7
- W7

## Scope

Files this task is expected to touch:

- `docs/milestones/retrieval-exit-check.md`: the checklist, step by step,
  on the skeleton's VPS upgraded to this milestone's image: upgrade, the
  model download, `tiroir admin eval` on stores from both presets, the bench
  report's reference, Claude Code with the plugin (latency seen from the
  hook, from the server log's durations), Claude Desktop with the memory
  skill uploaded and the snippet set, the C7 and W7 runs, and the two
  observations above; each step with what to record
- `docs/milestones/retrieval-scripts.md`: the C7 set (at least 12 prompts
  naming clients of `accounting-firm` by name, code or alias, in French, some
  indirect), the W7 sets (at least 12 conversations of two to four user turns
  that establish a decision, a deadline or a document received, and at least
  6 that establish nothing new), each with what counts as a pass
- `src/tiroir/core/skill.py`: only the skill's wording, if the run shows it
  falls short; each change and the rerun recorded in the checklist

Out of scope:

- the milestone review note (`etabli-decompose`, with the project owner,
  once every task is merged)
- automating C7 and W7 against the Claude API (a later improvement)

## Acceptance criteria

- The scripts and the checklist are in the pull request before the run, and
  the run's results are added to the checklist: per prompt and conversation,
  pass or fail, with the tool calls observed.
- C7 holds (≥ 9/10 rate on the run) and W7 holds (≥ 8/10, and 0 writes on
  the chatter set), or the checklist records the miss, the skill wording
  changes tried, and the task stops for the project owner to decide.
- The checklist records whether Claude Desktop declares `elicitation`, and
  whether the connector still works after the access token's lifetime (1
  hour) without signing in again.
- `mise run docs:build` passes; `mise run check` passes.

## Validation

The run of `docs/milestones/retrieval-exit-check.md` by the project owner,
`mise run docs:build`, then `mise run check`.
