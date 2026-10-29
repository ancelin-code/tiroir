# tiroir

**Configurable, scoped memory for AI agents.** *Tiroir* is French for *drawer*.

Give any AI agent a memory organised the way its user actually works. A developer
thinks in repositories, an accountant in client files, a consultant in
engagements. With tiroir, the organisation of memory is configuration: you
declare your drawers, and tiroir handles storage, indexing, retrieval, context
injection and sync.

**Documentation: [ancelin-code.github.io/tiroir](https://ancelin-code.github.io/tiroir/)**

> **Status: 0.1.0.** One server for a team, run with Docker Compose behind
> Caddy, administered from the command line, and connected to Claude Desktop
> with tools to search, read and log memory. More surfaces follow, milestone
> by milestone.

## Principles

- **Plain files are the truth.** Memory is readable Markdown in a Git
  repository. Every index is derived and rebuildable.
- **Your drawers, your schema.** Drawer types, layout, metadata, templates and
  injection rules are configuration, not code.
- **Isolation over recall.** When a drawer is active, retrieval stays inside
  it. Isolation between drawers is a tested guarantee.
- **Abstain rather than mislead.** Injecting nothing beats injecting a
  plausible but wrong memory.
- **You choose where your memory lives.** It syncs to a Git repository you
  pick, self-hosted or hosted. Nothing else leaves your machine: no telemetry,
  no third-party APIs, and embeddings are computed locally.
- **Git without Git.** tiroir syncs your memory across machines and team
  members through Git, and you never have to touch Git.
- **Humans own the synthesis.** Logs are append-only, and summaries change only
  after you confirm.

## Quickstart

On a VPS with Docker Compose and a domain name pointing to it:

```sh
git clone https://github.com/ancelin-code/tiroir.git && cd tiroir
cp .env.example .env    # set TIROIR_DOMAIN and TIROIR_ACME_EMAIL
docker compose pull && docker compose up -d
docker compose exec tiroir tiroir admin init
```

Then follow the documentation:

- [Install tiroir on a VPS](https://ancelin-code.github.io/tiroir/install/vps/):
  the stack, the first administrator, a member and a store.
- [Connect Claude Desktop](https://ancelin-code.github.io/tiroir/connect/claude-desktop/):
  add the server as a custom connector and sign in.
- [CLI reference](https://ancelin-code.github.io/tiroir/reference/cli/): the
  administration commands.

## Planned surfaces

- A member CLI and the Claude Code plugin with automatic context injection.
- A guided setup skill that interviews you and designs your schema.
- Presets beyond accounting firms, starting with developers.

## Contributing

`mise run check` runs every check, `mise run stack` builds the image from the
working tree and starts the stack, and `mise run docs:serve` previews the
documentation site.

## Project documents

- [Product brief](docs/brief.md): vision, principles and constraints.
- [Requirements](delivery/prd.md): what v1 must do, checkably.
- [Prior art review](docs/research/prior-art.md): what we learned from existing
  agent memory projects.
- [Skeleton exit check](docs/milestones/skeleton-exit-check.md): the checklist
  run against a real server at the end of the first milestone.

## Licence

[Apache-2.0](LICENSE).
