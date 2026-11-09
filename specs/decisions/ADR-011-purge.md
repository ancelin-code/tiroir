# ADR-011: Purge by rewriting the store's history on the server, masking links, recording salted digests, and force-pushing mirrors

**Status:** accepted
**Date:** 2026-10-22

## Context

A drawer, a log entry or a shared document must be removable from the store's
repository and its whole history, from the index, and from every configured
mirror (E1, E3); explicit links to it must be masked everywhere (E5); no write
may reintroduce it (E2, Y4e). Every write goes through the server, which holds
the only writable copy of each store (ADR-010).

## Decision

- **Preconditions:** the store's write lock is held for the whole purge;
  writes arriving meanwhile wait or are refused with `store.busy` (Y4d's
  rule).
- **Dry run:** lists the files removed, the files whose links to purged
  content are masked, the files that mention the purged drawer's names in
  plain text (left unchanged), the number of commits rewritten or dropped,
  and the mirrors that will be force-pushed. The purge itself needs a
  confirmation naming the drawer or entry (E1), through a proposal (ADR-012).
- **Rewrite:** `git filter-repo` on the bare repository (ADR-010), with a
  tiroir callback that: removes the purged paths from every commit; replaces
  every explicit link to a purged path with the text `[purged]` in the
  remaining files (ADR-014); removes the moves involving purged paths from
  `.tiroir/moves.yaml`; and replaces the message of every commit whose
  trailers reference a purged drawer with `tiroir: purged`. Commits left
  empty are dropped; authors and dates are kept.
- **Purge record:** the rewritten head gets one more commit adding an entry to
  `.tiroir/purges.yaml`: the next epoch number, the date, the author, a
  SHA-256 digest of each purged path salted with the store id, and the Git blob
  ids of the purged files and of the previous versions of the files whose
  links were masked. Paths and content never appear in the record.
- **Refusing reintroduction:** every write checks its target paths against the
  record's digests, and the blob of each file it writes against the record's
  blob ids (E2, Y4e). A new drawer created after the purge under the same path
  is allowed: it is new content.
- **Clean-up:** reflogs expired and `git gc --prune=now`, so the purged objects
  no longer exist on the server; a test asserts it. The index rows and every
  pending proposal touching the purged paths are deleted.
- **Mirrors:** the mirror pusher force-pushes the rewritten `main` to each
  mirror at once. A mirror that refuses (protected branch, unreachable) is
  listed on the administration page as holding purged content until a later
  push succeeds (E2).

## Alternatives considered

- **Delete in a new commit only** - leaves the content in every past commit;
  fails E1.
- **tiroir's own history rewriter on libgit2** (the local-first design, which
  had no `filter-repo`) - more code to get right; `git filter-repo` is the
  reference tool, is in the image, and accepts a callback for the link masking.
- **Encrypt each drawer and destroy the key to purge** (crypto-shredding) -
  avoids rewriting history, but makes clones and mirrors unreadable without
  tiroir (S5).
- **Recording purged paths in clear** - simplest to check, but publishes the
  very names (client names in paths) the purge is meant to erase, to every
  clone and mirror.

## Consequences

A purge rewrites commit ids: read-only clones must be re-cloned, which their
next fetch reveals, and the documentation says so. The guarantee stops at what
the server controls: read-only clones, server backups made before the purge,
and a mirror host's own caches (GitHub keeps cached views until a support
request) still hold the data; the documentation states this, recommends
self-hosted mirrors for stores that need erasure, and explains how to drop old
backups. Masking links changes files in other drawers, the one modification of
log entries the invariants allow (E4, E5).
