# ADR-010: Drive Git with dulwich over SSH deploy keys, keep history linear and sync by replaying operations

**Status:** proposed
**Date:** 2026-10-21

## Context

tiroir alone runs Git (Y1, Y8), on machines that may have no Git installed
(macOS without developer tools, Windows), with a credential it creates and
holds (Y7, Y8). Concurrent writes must never lose data or show a Git conflict
(Y4–Y4g), and outside edits are held back until confirmed (Y9, Y10).

## Decision

- **Library:** dulwich (pure Python). Verified on 2026-10-21: dulwich 1.2
  provides fetch, push, reset, merge, rebase and `filter_branch` (with index
  filters and empty-commit pruning, used by ADR-011).
- **SSH transport:** tiroir implements dulwich's `SSHVendor` interface on
  paramiko (dulwich 1.2 only ships vendors that call an `ssh` executable). No
  `git` or `ssh` executable is required.
- **Credential:** for each store on each machine, tiroir generates an Ed25519
  key pair in the data directory, readable by the user only. Connecting a
  store shows the public key and the host's page where to add it as a
  **deploy key with write access**; that is the one step on the host (Y7).
  Host keys are trusted on first use and pinned in tiroir's own known-hosts
  file.
- **Branch and history:** one branch per store (`main`), linear, never merged.
  Each tiroir operation is one commit. Commit messages follow the
  `store-layout` contract: an operation line and trailers (operation, drawer,
  author, base version), never memory content (Y5). The author recorded is
  the machine configuration's identity (Y4f).
- **Store lock:** a file lock per store in the data directory serialises Git
  operations and index writes across the MCP server, the hook and the CLI.
- **Sync:**
  1. Fetch. If the remote head descends from the local one, fast-forward.
  2. If local commits are unpushed and the remote moved, reset to the remote
     head and **replay** each local operation from its commit trailers and
     content: new files (log entries, new shared documents) are re-added;
     summary and shared-document changes are re-based on the new version
     (ADR-012), becoming proposals again when their base changed (Y4b);
     migrations are abandoned and re-planned (Y4d); writes into a drawer the
     remote has purged are refused and reported (Y4e).
  3. Push. On rejection, repeat from 1, at most three times, then keep the
     operations queued locally (Y4c).
  4. If the remote head does not descend from the last known remote head and
     no purge is recorded (ADR-011), stop and report: someone rewrote the
     history outside tiroir.
- **When:** at MCP server start and before every write (Y3), and on demand
  (`tiroir sync`). The hook never syncs.
- **Outside edits:** before every operation tiroir compares the working copy
  with the last commit. Differences become pending proposals of kind
  `outside-edit` (ADR-012); the files keep their edited content until the
  user confirms or restores them.

## Alternatives considered

- **The system `git` executable** - the most capable, but absent by default on
  Windows and on macOS without developer tools, where invoking it opens an
  install dialog, which fails the non-developer path.
- **pygit2 (libgit2)** - fast and complete, with SSH built in, but a native
  dependency whose SSH support varies by wheel and platform; dulwich's speed
  is ample at a few thousand commits.
- **Git's own merge (three-way merge commits)** - would surface textual
  conflicts in summaries; replaying tiroir's own operations knows what each
  change meant and turns conflicts into proposals.
- **HTTPS with a personal access token** - works where SSH is blocked, but
  the user must create, paste and renew a token, against Y7. See the
  consequences.

## Consequences

Sync is tiroir code, not Git's, so it is fully testable (Y4g) but also tiroir's
responsibility to get right. A deploy key grants one machine access to one
repository, so a machine with three stores holds three keys, and GitHub refuses
to reuse a deploy key across repositories, which this scheme never does.
Revoking a machine is deleting its deploy key on the host. Requirement Y6
allows HTTPS remotes; this record supports SSH only in v1 because HTTPS needs a
token the user handles. Y6 should be amended to "SSH" or HTTPS added later
with an OAuth device flow.
