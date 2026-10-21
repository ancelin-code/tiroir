# ADR-011: Purge by rewriting history, recording an epoch, and refusing stale content on every clone

**Status:** proposed
**Date:** 2026-10-21

## Context

A drawer, a log entry or a shared document must be removable from the working
copy, the index and the whole history, locally and on the remote (E1, E3), and
no other clone may bring it back (E2, Y4e). Git history is immutable by
design: removal means rewriting every commit since the content appeared, and
every clone must learn that the rewrite happened.

## Decision

- **Preconditions:** the store is synced, nothing is queued locally, and the
  store lock is held.
- **Dry run:** lists the files removed and the number of commits rewritten or
  dropped. The purge itself needs a confirmation naming the drawer or entry
  (E1), through the proposal mechanism (ADR-012).
- **Rewrite:** tiroir walks the branch from its root with libgit2 (ADR-010)
  and rebuilds each commit with the purged paths removed from its tree,
  dropping commits left empty, keeping authors and dates, and replacing the
  message of every commit whose trailers reference a purged drawer with
  `tiroir: purged`. libgit2 has no `filter-branch`, so this is tiroir code,
  covered by the same multi-clone tests as sync.
- **Purge record:** the rewritten head gets one more commit adding an entry to
  `.tiroir/purges.toml`: the next epoch number, the date, the author, a SHA-256
  digest of each purged path salted with the store id, and the Git blob ids of
  the purged files. Paths and content never appear in the record.
- **Publication:** force-push, only if the remote head is still the one the
  rewrite started from; otherwise abandon the rewrite and start over.
- **Local cleanup:** libgit2 has no garbage collection, so tiroir repacks the
  reachable objects into a new pack with libgit2's pack builder, deletes the
  old packs and the unreachable loose objects, and clears the reflogs. It also
  deletes the index rows and any pending proposal touching the purged paths. A
  test asserts that the purged blobs no longer exist in the local object
  store.
- **Other clones:** when a fetch finds a remote head that does not descend from
  the last known one and a higher epoch in `purges.toml`, tiroir resets to the
  remote, deletes the unreachable objects, and replays the queued local
  operations (ADR-010) except those based on a pre-purge commit that touch a
  purged path, which are refused and reported (Y4e).
- **Push guard:** tiroir refuses to push any commit containing a blob listed
  in `purges.toml` (E2). A new drawer created after the purge under the same
  path is allowed: it is new content, and refusing it would block a returning
  client forever.

## Alternatives considered

- **Delete in a new commit only** - removes the file from the current state but
  leaves it in every past commit; fails E1.
- **Encrypt each drawer and destroy the key to purge** (crypto-shredding) -
  avoids rewriting history, but makes the files unreadable without tiroir
  (S5) and needs key distribution to every team member.
- **`git filter-repo`** - the reference tool, but needs the `git` executable
  and Python (ADR-010).
- **Recording purged paths in clear** - simplest to check, but publishes the
  very names (client names in paths) the purge is meant to erase.

## Consequences

A purge rewrites commit ids: every clone must sync before writing again, which
tiroir does automatically. Path digests let someone who knows the store id
confirm a guessed path was purged; they do not reveal it. The guarantee stops
at what tiroir controls: a clone that never syncs again keeps the data, and a
Git host may keep unreachable objects until its own garbage collection runs
(GitHub requires a support request to purge cached views). The documentation
states this, recommends a self-hosted Forgejo for stores that need erasure,
and describes how to trigger its garbage collection. The host must allow the
force-push; the store's branch must not be protected against it.
