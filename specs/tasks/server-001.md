---
id: server-001
title: Run the server process with its database and first administrator
type: feat
epic: server
depends_on: [foundation-001]
parallel: true
conflicts_with: [server-002, server-003, server-004]
tier: build
review: [security]
---

## Context

The server is one Starlette application run by Uvicorn in a single process
([ADR-009](../decisions/ADR-009-server-process-model.md)), with its state in
`<data>/server.db` ([ADR-004](../decisions/ADR-004-server-members-and-access.md)).
This task creates the process, the database with the tables the skeleton
needs, the health route and the administration commands that create the
first administrator and members. Sign-in and OAuth are `server-002`'s; stores
and grants are wired by `server-003`.

## Covers

- A2 (part): the `members` and `grants` tables and the member records; grants
  are written by `server-003`, and per-store access checks come in the team
  milestone
- Y5 (part): server logs as JSON lines with no memory content, no query
  strings and no bodies

## Scope

Files this task is expected to touch:

- `src/tiroir/core/serverdb.py`: opens `<data>/server.db`, creates and
  versions its schema (a `schema_version` table and ordered migrations),
  tables `members` (id, handle, display name, password hash, is_admin,
  must_change_password, created, disabled), `grants` (member, store id,
  access), `stores` (id, name, audience, language, created), and functions to
  create, find and disable members; passwords hashed with Argon2id
- `src/tiroir/server/app.py`: the Starlette application factory
  `create_app(core_or_data_dir)`, `/health` per the
  [HTTP routes contract](../contracts/http-routes.md), JSON request logging
- `src/tiroir/server/logging.py`: the loguru set-up of ADR-002 (JSON lines on
  stdout, `diagnose=False`, standard library loggers routed into loguru)
- `src/tiroir/cli/admin.py`: `tiroir admin init` (creates the first
  administrator if none exists, prints their handle and a one-time sign-in
  link or initial password that must be changed), `tiroir admin members
  list|add|disable|reset-password`, `tiroir admin serve` (Uvicorn, one
  worker, port 8080, data dir from `TIROIR_DATA`, default `/data`), as in the
  [CLI contract](../contracts/cli.md)
- `src/tiroir/cli/main.py`: dispatch to `admin`
- `tests/integration/test_serverdb.py`, `tests/integration/test_health.py`,
  `tests/integration/test_admin_members.py`

Out of scope:

- sign-in pages, sessions, OAuth and tokens (`server-002`)
- stores, grants and the core facade (`server-003`)
- the administration web page (team milestone)

## Acceptance criteria

- `tiroir admin init` on an empty data directory creates `server.db` and one
  administrator, and a second run refuses with a clear message and exit 1.
- `tiroir admin members add bob --name "Bob Martin"` creates a member with an
  initial password flagged to be changed; `disable bob` sets `disabled`; a
  disabled or unknown handle is reported with exit code 1.
- Password hashes are Argon2id; no password appears in output except the
  one-time initial value, or in logs.
- `tiroir admin serve` starts the server; `GET /health` answers `200` with
  `{"status": "ready", "version": …}` and names no store.
- Each request logs one JSON line with method, path template, status,
  duration and member handle (empty here), never a query string or body.
- Opening a database created by an older schema version applies the missing
  migrations in order (tested with a fixture at version 0).
- `mise run check` passes.

## Validation

`mise run test -- tests/integration`, then
`mise run check`, then `uv run tiroir admin serve` and `curl
localhost:8080/health`.
