# ADR-004: Keep stores self-describing, and hold members, access and server state in one server database

**Status:** proposed
**Date:** 2026-10-22

## Context

One server serves one organisation: several stores and several members, each
member granted read-only or read-write access per store (A2, M1). A personal
store has exactly one member (M2), writes whose target is not implied go to
the member's personal store (M4), and a member never reaches a store they were
not granted (X1a). Every component needs to know who the member is (Y4f),
which stores they use and with what access, and none of this may leak into a
store's repository, which clones and mirrors copy (Y6, Y7).

## Decision

- **What belongs to the store** lives in its `tiroir.yaml` (contract
  `schema.md`): a store id (UUID generated at creation), a name (slug, unique
  on the server), the audience and the memory language. A store's repository
  holds nothing about members, access or the server.
- **What belongs to the server** lives in one SQLite database,
  `<data>/server.db`, written only by tiroir:
  - **members:** id, handle (slug used in log file names and commits, unique
    and never reused), display name, password hash, whether they are an
    administrator, created and disabled dates;
  - **grants:** member, store id, `read` or `write`. A `personal` store has
    exactly one grant, `write`; changing a store's audience is refused while
    it would break this;
  - **the member's default store** for writes whose target is not implied:
    their personal store when they have one, otherwise none, and such a write
    must then name its store (M4);
  - **credentials and sessions** (ADR-015), **proposals** (ADR-012),
    **mirror settings and state** (ADR-010), the **embedding choice per store**
    (ADR-006) and the **server settings** edited on the administration page.
- **Data directory** (`<data>`, the container's volume, ADR-016):
  `server.db`; `stores/<store-id>.git` (bare repositories, ADR-010);
  `index/<store-id>.sqlite` (ADR-005); `models/` (ADR-006); `secrets/`
  (mirror keys, the signing key of tokens). Store ids, not names, key every
  path, so renaming a store moves nothing.
- **Access is checked in the core**, never in a surface: every core call
  carries the calling member (contract `core-api.md`), and the core resolves
  the stores that member may read or write before doing anything else (X1a).
  The administration surface is the only caller allowed to act on stores the
  administrator holds no grant on, and it never reads memory content (A3).
- **Administrators** are members with the administrator flag. The first one is
  created by `tiroir admin init` when the server starts for the first time
  (ADR-016). An administrator reads a store's content only through a grant like
  any member; X4 documents that they can still read the disk.

## Alternatives considered

- **Members and grants in a YAML file next to the stores** - readable and easy
  to back up, but concurrent edits from the administration page need locking
  and validation the database gives for free, and it would hold password
  hashes in a file people edit.
- **Grants inside each store's repository** (a `members.yaml`) - travels with
  the store, but publishes the member list to every clone and mirror, and lets
  history, not the server, decide access.
- **Access enforced by Git host permissions** (the local-first design) - no
  Git host is involved any more; the server is the only door.
- **PostgreSQL** - better for many concurrent writers and for a later hosted
  offering, but a second container to run and back up, for a database written
  a few times a minute. The database access goes through one module so that it
  can be swapped when multi-organisation hosting comes.

## Consequences

A backup is the data directory without indexes and models (A6, ADR-016).
Removing a member disables their account and revokes their grants, tokens and
sessions at once (A4); their handle stays reserved so history keeps a single
meaning for it. Read-only clones they made keep what they already had
(documented, H1). A store moved to another server keeps its id, so its index
and links survive the move.
