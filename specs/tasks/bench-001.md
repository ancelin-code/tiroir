---
id: bench-001
title: Benchmark the server against the performance budgets on generated stores
type: feat
epic: bench
depends_on: [semantic-003, context-003]
parallel: true
conflicts_with: [semantic-001]
tier: build
review: []
---

## Context

The performance budgets (P1 to P4, P6) are measured on a reference server (4
vCPU, 8 GB RAM, no GPU, Linux) with a store of 500 drawers and 10,000 log
entries, and again with 2,000 drawers and 50,000 entries (P6). The presets
hold about 20 drawers, so the stores must be generated. ADR-002 names a
`bench` task, and ADR-006 chooses the default model on resident memory and
index time measured this way (`eval-003` runs this harness per candidate).

## Covers

- P1
- P2
- P3
- P4
- P6

## Scope

Files this task is expected to touch:

- `bench/generate.py`: a deterministic generator (seeded) of a store in the
  [store layout](../contracts/store-layout.md) from a preset's schema and
  vocabulary: `--drawers 500 --entries 10000` and `--drawers 2000 --entries
  50000`, with realistic lengths, names and identifiers, written as a store's
  files ready for `create_store`
- `bench/run.py`: starts the application on a data directory holding the
  generated store, signs a member in through OAuth as the integration tests
  do, and measures through the MCP client over HTTP: `tiroir_context` on a
  fixed list of prompts (P1), `tiroir_search` hybrid on a fixed list of
  queries (P2), each with 1 and with 10 concurrent clients; the full rebuild
  time and the time for an appended entry to be found (P3); the process's
  peak resident memory once the model and every vector are loaded (P4); a
  report in Markdown and JSON with the machine's description, p50/p95/max and
  pass or fail per budget
- `mise.toml`: `bench` (both store sizes) and `bench:quick` (a small store,
  for a laptop) tasks
- `docs/milestones/retrieval-bench.md`: the report of a run on a machine of
  the reference size (the skeleton's VPS class), with the command used
- `tests/integration/test_bench_generate.py`: the generator's output is a
  valid store with the requested counts

Out of scope:

- P7 (10 members concurrently, the team milestone; the 10-client run here is
  one member)
- optimising code paths beyond what a budget miss requires: a miss that needs
  a design change stops the task and is raised
- the per-model comparison (`eval-003`, which reuses this harness)

## Acceptance criteria

- `mise run bench` generates both stores, runs every measure and writes the
  report; `mise run bench:quick` finishes in under 5 minutes on a laptop.
- The report recorded in `docs/milestones/retrieval-bench.md`, from a 4 vCPU
  / 8 GB Linux machine with the provisional default model, shows P1, P2, P3,
  P4 and P6 met, or names the budget missed and the measured value, and the
  task stops there for the project owner to decide.
- The generator is deterministic: the same seed gives byte-identical files.
- `mise run check` passes (the benchmarks are not part of it).

## Validation

`mise run test -- tests/integration/test_bench_generate.py`, `mise run
bench:quick`, `mise run bench` on a reference-size machine, then
`mise run check`.
