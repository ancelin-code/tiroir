# ADR-009: Run a stdio MCP server per host session and a short-lived, model-free hook process, with no daemon

**Status:** proposed
**Date:** 2026-10-21

## Context

Per-prompt detection and injection must take at most 300 ms at p95 (P1), and
search at most 500 ms once running (P2). Measured on 2026-10-21 on 4 cores: a
bare Python process with `sqlite3` starts in about 10 ms, while importing
fastembed and loading the default model takes about 1.2 s. Cairn reaches its
hook budget with a resident daemon; agentcairn with a pre-warmed model and a
BM25 fallback. tiroir must stay light (no service to install or keep alive).

## Decision

- **MCP server:** started by the host over stdio, one process per host
  session, as hosts do by default. At start it integrates remote changes in
  the background (Y3) and loads the embedding model in a background thread;
  a search arriving before the model is ready runs lexically and says so.
- **Hook:** a short-lived `tiroir hook <host> <event>` process per event,
  launched from the installed `tiroir` executable, never through `uvx`. Its
  import path is restricted to the modules needed for detection and context
  building (configuration, schema, index reading, normalisation, matching,
  file reading). It never imports numpy, onnxruntime or fastembed, never
  touches the network and never runs Git operations. Its freshness check
  (ADR-005) updates text and names only.
- **Deadline:** the hook stops itself at 1.5 s and outputs nothing; the
  installed hook configuration sets the host timeout to 2 s (P1, C6).
- **No daemon** in v1. The CLI is a plain process like the hook.
- **Guarded in CI:** a test fails if the hook's import graph reaches a
  forbidden module, and a benchmark measures P1 on the three platforms.

## Alternatives considered

- **A resident daemon, with the hook as a thin socket client** (Cairn) - the
  fastest option and shares one loaded model across sessions, but it is a
  service to start, supervise and upgrade on three platforms, and it is not
  needed while the hook does no semantic work. It stays the fallback if the
  Windows benchmark misses P1.
- **The hook talks to the MCP server's process** - the host starts the MCP
  server, but hooks and server are not guaranteed to share a lifetime or to
  find each other, and Claude Desktop has no hooks at all.
- **Semantic recall in the hook** (agentcairn) - over a second per cold
  process, and the injection policy only needs the detected drawers'
  summaries, which require no embedding.

## Consequences

Each concurrent host session holds its own copy of the model (about 0.7 GB),
so three open Claude Code sessions use about 2 GB; P4 holds per process, and
the cost is documented. The hook injects drawer summaries, never search
results: semantic recall in Claude Code goes through the MCP search tool. "Once
per session" (C5a) is tracked by the hook with the host's session id and by
the MCP server for its own lifetime, so conventions can reach a session twice
at most, once through each path.
