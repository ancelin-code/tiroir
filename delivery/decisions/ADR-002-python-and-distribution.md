# ADR-002: Build tiroir in Python and distribute it through uv

**Status:** proposed
**Date:** 2026-10-21

## Context

Every component (core, MCP server, CLI, adapters) must share one runtime, and
the runtime decides how a non-developer installs tiroir in Claude Desktop
without a terminal (U4), how it runs on macOS, Windows and Linux (D1), and
which libraries are available for embeddings, Git and full-text search. The
project owner reviews Python fluently.

## Decision

- **Language:** Python, minimum version 3.12. One distribution package named
  `tiroir` on PyPI (the name is free as of 2026-10-21), exposing the `tiroir`
  command.
- **Runtime management:** `uv`. Users never install Python themselves:
  - Claude Desktop: an MCP Bundle (`.mcpb`) with server type `uv`, so Claude
    Desktop provisions Python and the dependencies from `pyproject.toml`.
    Installing it is a double-click.
  - Claude Code and terminal users: `uv tool install tiroir` installs the
    `tiroir` executable once; the Claude Code plugin's MCP server and hook run
    that executable. `uvx` is not used at run time: it costs 130 to 210 ms per
    launch (measured 2026-10-21), most of the hook's budget (ADR-009), and
    could run a different version for the hook and the server.
- **Pinned dependency set** (all with wheels for the three platforms, no
  compiler needed): the MCP Python SDK, `dulwich` and `paramiko` (Git,
  ADR-010), `fastembed` with `onnxruntime` (embeddings, ADR-006), `numpy`,
  `PyStemmer` (stemming, ADR-007), `ruamel.yaml` (schema round-trip,
  ADR-003), `platformdirs`, `filelock`.
- **Development:** `uv` for environments, `pytest`, `ruff`, and CI on macOS,
  Windows and Linux.

## Alternatives considered

- **TypeScript on Node** - Node ships inside Claude Desktop, so a `node` bundle
  needs no runtime at all, but local embeddings, stemming and pure-library Git
  are weaker in that ecosystem, and the owner reviews Python more easily.
  Since `.mcpb` gained the `uv` server type, Python no longer costs the user an
  install.
- **A single compiled binary (Go or Rust)** - smallest footprint and fastest
  start, but no mature local embedding stack comparable to fastembed/ONNX,
  and slower iteration for a project whose hard parts are retrieval tuning
  and schema handling.
- **Python with the system interpreter (`pip install`)** - fails the
  non-developer path: macOS ships no usable Python by default and Windows none
  at all.

## Consequences

The install footprint is a few hundred megabytes (onnxruntime, numpy, the
model) plus the model download, acceptable against P4 but not tiny. Python
start-up cost shapes the process model (ADR-009). The `uv` bundle type is
recent: the Desktop install path must be probed on macOS and Windows early,
and the `.mcpb` manifest version pinned to what Claude Desktop accepts.
