# ADR-016: Deploy with Docker Compose behind Caddy, keep all state in one data volume, and back up, restore and upgrade with tiroir commands

**Status:** proposed
**Date:** 2026-10-22

## Context

An administrator installs tiroir on a Linux VPS or on their own machine with
the same software and configuration (A1), behind HTTPS (A5), backs it up and
restores it elsewhere (A6), upgrades it with one command, migrating stored
formats automatically without losing the previous version's data on failure
(A7), and goes from a fresh VPS to a connected member in under 30 minutes
(P5). Claude Desktop, the web and mobile reach connectors from Anthropic's
infrastructure, so they need the server reachable from the internet.

## Decision

- **Stack:** `compose.yaml` in the repository, with two services:
  - `tiroir`: the image of ADR-002, one process (ADR-009), data in the volume
    `tiroir-data` mounted at `/data`;
  - `caddy`: the reverse proxy, obtaining and renewing certificates
    automatically for the domain set in `TIROIR_DOMAIN`, forwarding to
    `tiroir`. Streaming responses (MCP) are not buffered.
  Configuration is one `.env` file: domain, administrator e-mail for the
  certificate authority, image tag. Everything else is set on the
  administration page and kept in `server.db`.
- **First start:** `docker compose up -d`, then
  `docker compose exec tiroir tiroir admin init`, which creates the first
  administrator and prints a one-time sign-in link. The default model is
  downloaded in the background (ADR-006).
- **Own machine:** the same stack. Two documented ways to get HTTPS (A5):
  - a tunnel (for example Cloudflare Tunnel or Tailscale Funnel) giving a
    public HTTPS address, which every host can reach;
  - `TIROIR_DOMAIN=localhost`, where Caddy serves HTTPS with its own local
    certificate authority, whose root the administrator trusts on that
    machine; only Claude Code on that machine can then connect.
  tiroir ships no tunnel of its own.
- **Backup (A6):** `tiroir admin backup <file>` writes one archive of `/data`
  without `index/` and `models/`: `server.db` (copied with SQLite's online
  backup), the bare repositories (copied under each store's lock) and
  `secrets/`. Restore: `tiroir admin restore <file>` on a fresh volume, then
  indexes rebuild in the background. The documentation adds off-site copies
  and notes that backups keep purged content until they are dropped (E2).
- **Upgrade (A7):** `docker compose pull && docker compose up -d`. At start,
  the new version compares the format versions recorded in `server.db` and in
  each store; if a migration is needed, it first writes an automatic backup to
  `/data/backups/`, then migrates (database schema; store formats as one
  commit per store, I5), and starts serving only when all succeeded. On
  failure it stops, logs which step failed, and the documented rollback is the
  previous image tag plus that backup. Indexes are rebuilt when their format
  changes.
- **Logs:** to standard output, in JSON lines, with no memory content (Y5),
  for the container runtime to keep.

## Alternatives considered

- **A single container with its own TLS** (tiroir obtaining certificates) -
  one service less, but certificate handling is Caddy's job and well done
  there; tiroir stays plain HTTP inside the stack.
- **Kubernetes manifests or a Helm chart** - suits larger operators and a
  later hosted offering, but far beyond the target administrator; can be added
  around the same image.
- **A native installer or system package** - no container runtime needed on a
  VPS, but per-distribution packaging and dependency drift, against A1's single
  configuration.
- **A tunnel built into tiroir** - one step less for the own-machine case, but
  ties tiroir to a tunnel provider and puts a public entry point into the
  server's code.

## Consequences

The administrator needs a container runtime, a domain name pointing at the
VPS, and ports 80 and 443 open; the installation guide starts with these. The
own-machine path for Claude Desktop depends on a third-party tunnel, which the
documentation presents as such. All state is in one volume, so moving a server
is a backup and a restore. Automatic backups before upgrades consume disk; the
maintenance worker keeps the last three.
