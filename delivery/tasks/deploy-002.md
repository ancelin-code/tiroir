---
id: deploy-002
title: Write the skeleton installation guide and run the exit check
type: docs
epic: deploy
depends_on: [deploy-001, server-004]
parallel: true
conflicts_with: [deploy-001]
tier: build
review: []
---

## Context

The skeleton milestone ends when a real deployment passes its exit criterion
([decomposition](../decomposition.md#skeleton)): a VPS with a domain, a store
from the preset, Claude Desktop connected and signed in, a log entry appended
and found. This task writes the guide an administrator follows to get there,
and an exit checklist that the milestone review will run against a real
server. It also records what the first real connection teaches, since ADR-013
and ADR-015 list checks to make against the Claude hosts.

## Covers

- U4 (part): documented steps to add the server as a custom connector in
  Claude Desktop and sign in, with nothing installed; the web, mobile and the
  full member documentation come in later milestones
- A1 (part): the VPS installation path, from prerequisites to a running
  server

## Scope

Files this task is expected to touch:

- `docs/install/vps.md`: prerequisites (a Linux VPS with a container runtime,
  a domain name pointing to it, ports 80 and 443 open), `.env`, `docker
  compose up -d`, `tiroir admin init`, creating a member and a personal store
  from the preset, upgrading the image (pull and up) as it stands in this
  milestone
- `docs/connect/claude-desktop.md`: adding the custom connector with the
  server's address, signing in, a first search and a first log entry
- `docs/milestones/skeleton-exit-check.md`: the exit criterion as a numbered
  checklist with what to record at each step (versions of the image and of
  Claude Desktop, timings, the commit seen in the store's history via `docker
  compose exec tiroir git -C /data/stores/<id>.git log -1`)
- `README.md`: a short "Install" section linking the guides

Out of scope:

- running the checklist on a real VPS: that is the milestone review's job,
  with the project owner
- documentation of later features (own-machine setups, backups, mirrors,
  Claude Code plugin)

## Acceptance criteria

- Following `docs/install/vps.md` on a fresh local stack (`TIROIR_DOMAIN=
  localhost`) reproduces every step up to the creation of the store, with each
  command copied from the guide; the pull request lists the commands run and
  their output.
- The connector guide names every field Claude Desktop asks for and what to
  enter, and states what the sign-in and consent pages look like.
- The exit checklist covers every clause of the skeleton's exit criterion and
  says what evidence to record for each.
- Every link in the new documents resolves.

## Validation

Run the guide on a local stack as described, and check links with
`mise run check` (add a link check to the `check` task if none exists).
