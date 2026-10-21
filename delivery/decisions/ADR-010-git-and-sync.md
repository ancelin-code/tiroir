# ADR-010: Drive Git with libgit2 over SSH or HTTPS, keep history linear and sync by replaying operations

**Status:** proposed
**Date:** 2026-10-21

## Context

tiroir alone runs Git (Y1, Y8), on machines that may have no Git installed
(macOS without developer tools, Windows), with a credential it creates and
holds (Y7, Y8). Concurrent writes must never lose data or show a Git conflict
(Y4–Y4g), and outside edits are held back until confirmed (Y9, Y10).

## Decision

- **Library:** libgit2 through the `git2` crate, with libgit2 and libssh2
  vendored and linked into the binary (ADR-002). It provides clone, fetch,
  push, commits, trees and revision walking; tiroir builds sync and purge on
  them. No `git` or `ssh` executable is required.
- **Transports:** SSH and HTTPS (Y7a).
  - SSH: libssh2. Host keys are checked in libgit2's certificate callback,
    trusted on first use and pinned in tiroir's own known-hosts file.
  - HTTPS: libgit2's platform TLS (WinHTTP on Windows, the system TLS stack on
    macOS, OpenSSL with the system certificate locations on Linux), so the
    certificate authorities installed by a company's TLS inspection are
    accepted. Proxies come from libgit2's automatic detection or from tiroir's
    configuration.
- **Credential, one per store and machine, set up once (Y7):**
  - SSH: tiroir generates a key pair (Ed25519, or ECDSA P-256 on a platform
    where the bundled libssh2 lacks Ed25519) and shows the public key with the
    host's page where to add it as a **deploy key with write access**. The
    private key never leaves the machine.
  - HTTPS: the user creates a token limited to the store's repository with
    read and write access to its content (GitHub fine-grained token, GitLab
    project access token; on Forgejo, a token of a dedicated account that
    only has access to that repository) and pastes it once into tiroir. The
    connect flow links to the exact page and lists the permissions to tick.
  - Both are stored in the OS credential store (`keyring` crate: macOS Keychain,
    Windows Credential Manager, Secret Service on Linux), falling back to a
    user-only file in the data directory where none is available. Expiry
    dates the host reports are recorded, and `doctor` and the status tool
    warn 14 days ahead.
- **Choice of transport:** the remote URL decides. `store connect` tries the
  URL given; when an SSH connection times out, it says SSH is probably
  blocked and offers the HTTPS URL of the same repository.
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
- **gitoxide (`gix`)** - pure Rust and the better long-term fit, but push is
  not implemented as of 2026-10-21 (its status page lists push, send-pack and
  receive-pack as missing). To be reconsidered when it is, behind the same
  internal Git interface.
- **dulwich (pure Python)** - the choice of the Python design (ADR-002), not
  usable from Rust.
- **Git's own merge (three-way merge commits)** - would surface textual
  conflicts in summaries; replaying tiroir's own operations knows what each
  change meant and turns conflicts into proposals.
- **SSH only** - the simplest credential story, but corporate networks
  commonly block outbound SSH, which would leave those users unable to sync.
- **HTTPS through an OAuth device or browser flow** - no token to copy, but
  every host needs a registered OAuth application (each self-hosted Forgejo
  too), and the broad scopes OAuth apps get on GitHub reach far beyond one
  repository. Kept as a later improvement of the HTTPS step.

## Consequences

Sync is tiroir code, not Git's, so it is fully testable (Y4g) but also tiroir's
responsibility to get right. libgit2 brings C code (and OpenSSL on Linux) into
the build; its TLS and SSH behaviour per platform is verified early with real
remotes behind a proxy and with SSH blocked. A deploy key grants one machine access to one
repository, so a machine with three stores holds three keys, and GitHub refuses
to reuse a deploy key across repositories, which this scheme never does.
Revoking a machine is deleting its deploy key or token on the host. HTTPS
tokens expire on most hosts, so a store over HTTPS needs a renewal step
every few months; tiroir warns and guides it, but cannot avoid it. Forgejo has
no repository-scoped token, hence the dedicated-account recipe in the
documentation.
