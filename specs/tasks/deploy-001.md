---
id: deploy-001
title: Build the container image and the Compose stack behind Caddy
type: build
epic: deploy
depends_on: [server-001]
parallel: true
conflicts_with: [deploy-002]
tier: build
review: []
---

## Context

tiroir ships as one container image run by Docker Compose behind Caddy, which
obtains certificates automatically, with all state in one volume
([ADR-016](../decisions/ADR-016-deployment.md)); the image follows ADR-002's
lightness rules ([ADR-002](../decisions/ADR-002-python-and-container-distribution.md)).
The server process and `/health` exist since `server-001`.

## Covers

- A1 (part): the stack runs on a Linux VPS; the own-machine setups and their
  documentation come in the operations milestone
- A5
- D1 (part): the image is built for `linux/amd64` and `linux/arm64`

## Scope

Files this task is expected to touch:

- `Dockerfile`: multi-stage, Python 3.13 slim base, `git` installed,
  `uv sync --frozen --no-dev` into a virtual environment, non-root user, data
  volume at `/data`, entry point `tiroir admin serve`, health check on
  `/health`
- `compose.yaml`: services `tiroir` (image tag from `.env`, volume
  `tiroir-data`) and `caddy` (ports 80 and 443, volumes for its data and
  config), MCP streaming responses not buffered
- `deploy/Caddyfile`: reverse proxy to `tiroir:8080` for `{$TIROIR_DOMAIN}`,
  e-mail from `{$TIROIR_ACME_EMAIL}`
- `.env.example`, `.dockerignore`
- `.github/workflows/image.yml`: build both architectures on pull requests;
  on tags, push to `ghcr.io` with build provenance attestations; fail when the
  compressed image exceeds 600 MB
- `mise.toml`: tasks `image` (local build) and `stack` (`docker compose up`)
- `tests/integration/test_compose_config.py` (static checks of `compose.yaml` and
  the Caddyfile)

Out of scope:

- backup, restore and upgrade commands (operations milestone)
- the installation guide (`deploy-002`)
- PyTorch or any GPU runtime (forbidden by ADR-002)

## Acceptance criteria

- `mise run image` builds the image locally; its compressed size is printed
  and is under 600 MB; the image runs as a non-root user.
- With `TIROIR_DOMAIN=localhost` locally, `docker compose up -d` starts both
  services, `https://localhost/health` answers `200` through Caddy's local
  certificate authority (`curl --cacert` with Caddy's root), and `http://`
  redirects to `https://`.
- The `tiroir` service is not published on any host port; only Caddy is.
- Data written by `docker compose exec tiroir tiroir admin init` survives
  `docker compose down && docker compose up -d`.
- The image workflow builds both architectures on the pull request.
- `mise run check` passes.

## Validation

`mise run image`, `mise run stack`, `curl` against `/health`, and the image
workflow run on the pull request.
