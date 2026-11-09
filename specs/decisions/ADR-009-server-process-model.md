# ADR-009: Run one server process holding the model once, with background workers, and serve the prompt hook as an MCP tool call

**Status:** accepted
**Date:** 2026-10-22

## Context

Per-prompt detection and injection must take at most 300 ms at p95 seen from
Claude Code (P1), search at most 500 ms seen from the client (P2), with ten
members at once (P7), within 4 GB for the whole server (P4). A write must be
visible to search within 2 s (P3, W4), and embeddings cost tens of
milliseconds per chunk. Concurrent writes to one store must be serialised
(Y4), and administration commands run in the same container as the server.

## Decision

- **One application process** per server: Uvicorn running the Starlette
  application with a single worker process, so the embedding model and the
  vectors of every store are loaded once and shared by all members. Requests
  are handled on the event loop; anything CPU-bound or blocking (embedding a
  query, vector scan, SQLite, Git) runs in a bounded thread pool. ONNX Runtime
  and NumPy release the GIL while computing.
- **Background workers**, threads of the same process:
  - **indexer:** after each commit, updates text, names and links
    immediately, then embeds the new chunks; lexical search sees a write at
    once, semantic search once its embeddings land (ADR-005);
  - **mirror pusher:** pushes each store's new commits to its mirrors, with
    retries (ADR-010);
  - **maintenance:** expires proposals and sessions, and repacks
    repositories.
- **Store write lock:** one lock per store serialises its writes, migrations
  and purges. It is a file lock (`fcntl`) on `<data>/locks/<store-id>`, so the
  administration CLI, which runs as a separate process in the container
  (`tiroir admin …`), takes the same lock as the server. Reads never take it.
- **Model loading:** at start, in the background. A search arriving before the
  model is ready runs lexically and says so. A store using an external
  embedding service (ADR-006) has no local model to wait for.
- **The prompt hook is an MCP tool call:** the Claude Code plugin declares a
  hook of type `mcp_tool` that calls `tiroir_context` on the plugin's tiroir
  MCP server (ADR-013, contract `claude-code-hook.md`). It reuses the
  session's authenticated MCP connection; there is no separate hook endpoint
  or token. The context path never embeds: it reads the names table and the
  summaries, both in memory or in SQLite.
- **Deadline:** `tiroir_context` stops at 1.2 s and returns an empty result;
  the plugin sets the hook timeout to 2 s, after which Claude Code discards the
  output and continues (P1, C6).
- **Health:** `/health` reports readiness (database, stores, model) for the
  container runtime and the administration page.

## Alternatives considered

- **Several worker processes** - more parallelism, but each loads the model
  and the vectors, multiplying memory against P4; one process with a thread
  pool covers P7.
- **A separate embedding service** (a model server container) - isolates the
  model, but a second container, a network hop per query and twice the
  configuration, for one server serving one organisation.
- **A task queue (Redis, Celery)** - durable background jobs, but another
  service; indexing is derived and can always be redone from the commits
  (R7), so losing an in-flight job on restart costs a re-index, not data.
- **An HTTP hook** (`type: http`) - the same request without MCP, but Claude
  Code substitutes plugin settings into neither its URL nor, reliably, its
  headers, so each member would have to set the server address and a token in
  their environment by hand, which fails U2.
- **A command hook running a local client** - works everywhere, but puts a
  program back on every developer's machine.

## Consequences

The server's memory is the model, the vectors of every store and the
interpreter, measured against P4 with P6's store. A crash of the process stops
every member at once; the container runtime restarts it, and the indexer
catches up from the last indexed commit of each store. Ten members' searches
share one thread pool, whose size is a setting checked by the P7 benchmark.
Conventions are delivered once per session (C5a) by the server itself, keyed
by the MCP session, whether they leave through the hook or through a tool call.
