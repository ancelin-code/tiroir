# tiroir

**Configurable, scoped memory for AI agents.** *Tiroir* is French for *drawer*.

Give any AI agent a memory organised the way its user actually works. A developer
thinks in repositories, an accountant in client files, a consultant in
engagements. With tiroir, the organisation of memory is configuration: you
declare your drawers, and tiroir handles storage, indexing, retrieval, context
injection and sync.

> **Status: design phase.** Nothing is usable yet. The requirements are being
> written; code follows once the design is approved.

## Principles

- **Plain files are the truth.** Memory is readable Markdown in a Git
  repository. Every index is derived and rebuildable.
- **Your drawers, your schema.** Drawer types, layout, metadata, templates and
  injection rules are configuration, not code.
- **Isolation over recall.** When a drawer is active, retrieval stays inside
  it. Isolation between drawers is a tested guarantee.
- **Abstain rather than mislead.** Injecting nothing beats injecting a
  plausible but wrong memory.
- **Local and private.** No telemetry, no third-party APIs. Embeddings run on
  your machine. The only network traffic goes to your own Git remote.
- **Git without Git.** tiroir syncs your memory across machines and team
  members through Git, and you never have to touch Git.
- **Humans own the synthesis.** Logs are append-only, and summaries change only
  after you confirm.

## Planned surfaces

- An MCP server for Claude Desktop and Claude Code.
- A Claude Code adapter with automatic context injection.
- A guided setup skill that interviews you and designs your schema.
- A CLI for setup, indexing, search, validation, sync, migration and erasure.
- Presets for developers and accounting firms, with synthetic data.

## Project documents

- [Product brief](brief.md): vision, principles and constraints.
- [Requirements](delivery/prd.md): what v1 must do, checkably.
- [Prior art review](docs/research/prior-art.md): what we learned from existing
  agent memory projects.

## Licence

[Apache-2.0](LICENSE).
