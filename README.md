<p align="center">
  <img src="docs/assets/logo.svg" alt="Tiroir logo: a wooden chest of drawers" width="120">
</p>

<h1 align="center">Tiroir</h1>

<p align="center">
  <a href="https://github.com/ancelin-code/tiroir/releases/latest"><img alt="Release" src="https://img.shields.io/github/v/release/ancelin-code/tiroir"></a>
  <a href="https://github.com/ancelin-code/tiroir/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/ancelin-code/tiroir/actions/workflows/ci.yml/badge.svg"></a>
  <a href="https://github.com/ancelin-code/tiroir/actions/workflows/docs.yml"><img alt="Docs" src="https://github.com/ancelin-code/tiroir/actions/workflows/docs.yml/badge.svg"></a>
  <a href="LICENSE"><img alt="License: Apache-2.0" src="https://img.shields.io/github/license/ancelin-code/tiroir"></a>
  <img alt="Python 3.13+" src="https://img.shields.io/badge/python-3.13%2B-blue">
  <a href="https://github.com/ancelin-code/tiroir/pkgs/container/tiroir"><img alt="Container image" src="https://img.shields.io/badge/ghcr.io-amd64%20%7C%20arm64-informational"></a>
</p>

**Configurable, scoped memory for AI agents.** *Tiroir* is French for *drawer*.

Give any AI agent a memory organised the way its user actually works. A developer
thinks in repositories, an accountant in client files, a consultant in
engagements. With Tiroir, the organisation of memory is configuration: you
declare your drawers, and Tiroir handles storage, indexing, retrieval, context
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
- **Git without Git.** Tiroir syncs your memory across machines and team
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

- [Installation Guide](https://ancelin-code.github.io/tiroir/install/vps/):
  the stack, the first administrator, a member and a store.
- [Connect Claude Desktop](https://ancelin-code.github.io/tiroir/connect/claude-desktop/):
  add the server as a custom connector and sign in.
- [CLI Reference](https://ancelin-code.github.io/tiroir/reference/cli/): the
  administration commands.

## Planned surfaces

- A member CLI and the Claude Code plugin with automatic context injection.
- A guided setup skill that interviews you and designs your schema.
- Presets beyond accounting firms, starting with developers.

The [Roadmap](https://ancelin-code.github.io/tiroir/roadmap/) says what each milestone brings.

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

The documentation site sets its headings in [Daubenton](https://velvetyne.fr/fonts/daubenton/),
by Olivier Dolbeau ([Velvetyne](https://velvetyne.fr/)), under the SIL Open Font
License 1.1 (`docs/assets/fonts/OFL-Daubenton.txt`).
