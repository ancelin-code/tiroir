# ADR-010: Keep each store as a bare Git repository on the server, written by tiroir alone, cloned read-only and copied to mirrors

**Status:** accepted
**Date:** 2026-10-22

## Context

Every store is a Git repository held by the server (Y1). Only tiroir writes to
it (invariant), concurrent writes never lose data or show a conflict
(Y4–Y4g), technical members may clone it read-only (Y7), and the
administrator may copy it to outside Git remotes (Y6). A purge rewrites
history (E1, ADR-011). Members never run Git.

## Decision

- **One bare repository per store**, `<data>/stores/<store-id>.git`, one
  branch `main`, linear history. There is no working copy: tiroir reads files
  from commits and writes new commits directly, so nothing can be edited
  outside tiroir on the server, and there are no outside edits to detect.
- **Writing:** under the store's write lock (ADR-009), tiroir reads the head,
  builds the new tree from it with the operation's changes, writes one commit
  with the `store-layout` message and trailers, and moves `main` with a
  compare-and-swap on the old head. Library: `pygit2` (libgit2) for objects,
  trees, commits and references. Author and committer are the member's display
  name with `<handle>@tiroir.invalid` (Y4f).
- **Concurrency:** writes to one store are serialised by the lock, so a log
  append always lands on the latest head and never conflicts (Y4a). A summary
  or shared-document proposal records the blob it was made against; if the
  file changed before confirmation, ADR-012's section merge applies (Y4b). A
  migration holds the lock for its whole run; writes arriving meanwhile wait
  up to 10 s, then are refused with `store.busy` and a retry message, and the
  agent retries (Y4d). Nothing is queued on a member's side, because members
  hold no copy.
- **Read-only clones (Y7):** served by `git http-backend` (the `git` executable
  in the image) under `/git/<store-name>.git`, behind tiroir's authentication:
  a member's personal access token (ADR-015) with a `read` or `write` grant on
  the store may fetch; `git-receive-pack` is refused for everyone. Clones use
  HTTPS only.
- **Mirrors (Y6):** per store, any number of outgoing remotes configured on
  the administration page, over SSH (a key pair the server generates per
  mirror, the public key shown to add as a deploy key with write access) or
  HTTPS (a token the administrator pastes, stored in `<data>/secrets/`). The
  mirror pusher (ADR-009) runs `git push --force` of `main` after each commit
  and after a purge; failures are retried with backoff and shown as lag on
  the administration page. Proxy and certificate authorities come from the
  container's environment. Mirrors never feed anything back into the store.
- **History checks:** at start and in `doctor`, every commit on `main` since
  the last check must carry tiroir's trailers; anything else means the
  repository was changed on disk outside tiroir, and the store is put
  read-only until the administrator resolves it.
- **Maintenance:** the `git` executable repacks repositories in the
  background and runs the purge clean-up (ADR-011).

## Alternatives considered

- **A working copy per store** (the local-first design) - lets people edit
  files on the server, which then need detection and confirmation (the old
  Y9, Y10); no member has shell access to the server, so the working copy only
  adds states to handle.
- **The `git` executable for every write** - one tool for everything, but a
  process per commit and plumbing commands to build trees; `pygit2` does it
  in-process, and the executable stays for what libgit2 does not provide:
  serving clones, `gc` and `filter-repo`.
- **A Git server (Forgejo, Gitea) in the stack** to serve clones and hold the
  repositories - mature and browsable, but a second set of accounts and access
  rules to keep in step with tiroir's, and a web interface showing memory
  content, which A3 excludes.
- **Writable clones with server-side checks** - the owner chose read-only
  clones for v1 (out of scope: writing through Git).
- **Subversion, Mercurial, Fossil, Pijul, file synchronisation, a CRDT store**
  - weighed in the local-first design for offline sync between machines, a
  need that is gone; Git remains what Obsidian users, mirrors and backup
  tools already understand.

## Consequences

A store's history is linear and every commit is a tiroir operation, so sync
logic, replays and the queue of unpushed changes of the local-first design are
gone. The `git` executable and `git-filter-repo` are part of the image, which
the image-size rule of ADR-002 accounts for. A mirror is a copy the purge
reaches only if it accepts a forced push (E2): its branch must not be
protected, and the administration page shows a mirror that refused.
