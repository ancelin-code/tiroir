# ADR-009: Run a stdio MCP server per host session and a short-lived, model-free hook process, with no daemon

**Status:** proposed
**Date:** 2026-10-21

## Context

Per-prompt detection and injection must take at most 300 ms at p95 (P1), and
search at most 500 ms once running (P2). A native binary starts in a few
milliseconds, but loading the default embedding model costs about 0.7 s
whatever the language (ONNX Runtime session creation; measured 2026-10-21,
ADR-006). Cairn meets its hook budget with a resident daemon. tiroir must stay
light: no service to install or keep alive.

## Decision

- **MCP server:** started by the host over stdio (`tiroir mcp`), one process
  per host session, as hosts do by default. At start it integrates remote
  changes in the background (Y3) and loads the embedding model on a
  background task; a search arriving before the model is ready runs lexically
  and says so.
- **Hook:** a short-lived `tiroir hook <host> <event>` process per event, run
  from the installed binary. Its code path covers only detection and context
  building: configuration, schema, index reading, normalisation, matching and
  file reading. It never initialises ONNX Runtime or opens a model, never
  touches the network and never runs Git operations. Its freshness check
  (ADR-005) updates text and names only.
- **Deadline:** the hook stops itself at 1.5 s and outputs nothing; the
  installed hook configuration sets the host timeout to 2 s (P1, C6).
- **No daemon** in v1. The CLI is a plain process like the hook.
- **Guarded in CI:** a test runs the hook with the model files absent and
  asserts a complete result, and a benchmark measures P1 on the three
  platforms.

## Alternatives considered

- **A resident daemon, with the hook as a thin socket client** (Cairn) -
  shares one loaded model across sessions, but it is a service to start,
  supervise and upgrade on three platforms, and it is not needed while the
  hook does no semantic work.
- **The hook talks to the MCP server's process** - the host starts the MCP
  server, but hooks and server are not guaranteed to share a lifetime or to
  find each other, and Claude Desktop has no hooks at all.
- **Semantic recall in the hook** (agentcairn) - pays the model load on every
  prompt, and the injection policy only needs the detected drawers'
  summaries, which require no embedding.

## Consequences

Each concurrent host session holds its own copy of the model (about 0.7 GB
measured with the Python stack, to be re-measured), so several open Claude
Code sessions multiply it; P4 holds per process, and the cost is documented.
If it proves too heavy, a shared model process is the upgrade path, without
changing the hook. The hook injects drawer summaries, never search results:
semantic recall in Claude Code goes through the MCP search tool. "Once per
session" (C5a) is tracked by the hook with the host's session id and by the
MCP server for its own lifetime, so conventions can reach a session twice at
most, once through each path.
