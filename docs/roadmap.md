# Roadmap

Tiroir is delivered in **milestones**: four slices of the product, each working
from end to end on a real server. A milestone ends with a check on a running
server and a review of what it taught, and only then is the next one cut. This
page says where Tiroir stands, what each milestone brings, and what 0.1.0 cannot
do yet.

No dates are promised. A milestone ships when its check holds, and the
[Changelog](changelog.md) records each release.

## Where we are

**Tiroir 0.1.0, released on 29 October 2026, delivers the first milestone.** The
second, *Retrieval*, is next, and is being prepared. The four milestones lead to
[Tiroir 1.0.0](#the-path-to-100).

| Milestone | Status | What it brings |
|---|---|---|
| [1. Skeleton](#1-skeleton) | <span class="status status-done">Delivered in 0.1.0</span> | A server that works end to end: install, sign in, search, log |
| [2. Retrieval](#2-retrieval) | <span class="status status-next">Next</span> | Search by meaning, and memory that Claude uses by itself |
| [3. Team](#3-team) | <span class="status status-planned">Planned</span> | Several members, safe shared writing, and a guided setup |
| [4. Operations](#4-operations) | <span class="status status-planned">Planned</span> | A server you can keep, back up, upgrade and erase from |
| [1.0.0](#the-path-to-100) | <span class="status status-goal">Goal</span> | The four milestones delivered and reviewed |

## The path to 1.0.0 { #the-path-to-100 }

Tiroir **1.0.0 is the release at the end of the fourth milestone**: the one where
everything planned for the first version exists, and each milestone has been
checked on a running server and reviewed.

```text
0.1.0 ───▶ Retrieval ───▶ Team ───▶ Operations ───▶ 1.0.0
Skeleton                                            the goal
```

Each milestone ends in a release numbered `0.x`. Until 1.0.0, treat the releases
as early ones and read the [Changelog](changelog.md) before you upgrade.

When 1.0.0 is out, you will be able to:

- install a server on a VPS or on your own machine, with documentation that
  takes a new administrator to a connected member in under 30 minutes;
- give each member exactly the stores they should reach, and let them use those
  stores from Claude Desktop, Claude on the web and mobile, and Claude Code;
- search by meaning as well as by keyword, and have Claude use the memory
  without being asked;
- shape a store with a guided setup, and change its schema later;
- back up a server, restore it on another machine, upgrade it with one command,
  and erase what must be erased.

Some principles hold at every release, and will still hold at 1.0.0:

- Plain Markdown files in a Git repository are the only source of truth. Every
  index can be rebuilt from them.
- Nothing leaves your server except to the mirrors and the external embedding
  service you configure, for certificate issuance, and to fetch the public
  description of an application that connects. There is no telemetry.
- A member never reaches a store they were not granted, and nothing is written to
  a team store without confirmation.
- No memory content appears in commit messages, logs or error messages.

## 1. Skeleton { #1-skeleton }

<span class="status status-done">Delivered in 0.1.0</span>

The foundations: a server you install, members who sign in, and Claude Desktop
reading and writing their memory.

- Install the server on a VPS with Docker Compose, behind HTTPS that Caddy
  obtains by itself.
- Members sign in with a password you give them; Claude Desktop connects as a
  custom connector.
- Stores are Git repositories of Markdown files, created from a preset, and the
  bundled `accounting-firm` preset comes with an invented dataset.
- Claude searches by keyword, reads drawers and appends log entries, and each
  entry is one commit.

It was checked on a real VPS: a member added a log entry from Claude Desktop and
found it by search within two seconds. Start with the
[Installation Guide](install/vps.md).

## 2. Retrieval { #2-retrieval }

<span class="status status-next">Next</span>

Finding the right memory, and having Claude use it without being asked.

- **Search by meaning**, combined with keyword search, in French and in other
  languages, with filters by drawer type, drawer, field and date. The default
  model is the one that scores best on a published evaluation, within a 4 GB
  budget.
- **Claude Code**: a plugin, installed in one command, that recognises the
  drawer a prompt is about and puts its summary in front of Claude in under
  300 ms.
- **A memory skill for Claude Desktop**, so that Claude searches Tiroir when it
  should and records what is worth remembering without being asked.
- **A second bundled preset, for developers**, next to `accounting-firm`.
- **A folder for your own presets**, that the server reads directly: no copying
  presets out of the image, no override file.

*The check:* on the milestone-one server, the evaluation reports how well
keyword, semantic and combined search find the right entry, and Claude Code and
Claude Desktop use Tiroir on a scripted set of prompts.

## 3. Team { #3-team }

<span class="status status-planned">Planned</span>

From one person's server to an organisation's.

- **Several members with different access**: each member reaches only the stores
  they were granted, read-only or read-write.
- **Safe shared writing**: a write to a team store is shown to the member and
  recorded only after they confirm, and two members writing at once lose
  nothing.
- **Members create drawers and update summaries from Claude.** An update is
  proposed, shown as a change, and applied after a person confirms it.
- **A guided setup**: Claude interviews a member in their language, proposes a
  schema, shows what it will create and writes it only after they agree. A
  non-developer ends with a working store without editing a file.
- **A web administration page** for members, stores and access, instead of the
  command line. It never shows memory content.

*The check:* two members with different grants use one server, each reaching
only their stores, and a non-developer completes the guided setup.

## 4. Operations { #4-operations }

<span class="status status-planned">Planned</span>

What makes a server safe to keep for years.

- **Erasure**: purge a drawer from the store, its history, the search index and
  a mirror, and mask the links that pointed to it.
- **Links** between drawers, listed for each one.
- **Schema changes**: add or rename a field, rename a drawer type or change the
  folder layout on an existing store, previewed before it is applied.
- **Read-only clones and mirrors**: a technical member clones a store, and a
  store is mirrored to another Git server.
- **Backup, restore and upgrade**: back up a server, restore it on another
  machine and upgrade it with one command, with the data migrated.
- **Documentation complete enough** for a new administrator to go from a fresh
  VPS to a connected member in under 30 minutes.

*The check:* a purge, a migration, a restore on another machine and an upgrade
all succeed.

## What 0.1.0 cannot do yet

| Limit in 0.1.0 | Planned in |
|---|---|
| Search is by keyword only. | [Retrieval](#2-retrieval) |
| No Claude Code plugin; no memory skill for Claude Desktop. | [Retrieval](#2-retrieval) |
| Your own presets need copying the bundled ones out of the image. | [Retrieval](#2-retrieval) |
| Members cannot create drawers or update summaries from Claude, only add log entries. | [Team](#3-team) |
| No guided setup: the schema is written by hand. | [Team](#3-team) |
| Administration is by command line only. | [Team](#3-team) |
| The schema of an existing store cannot be changed. | [Operations](#4-operations) |
| No backup, restore or upgrade commands, and no erasure. | [Operations](#4-operations) |

## Not planned for now

- A web interface to read or edit memory. The web administration page manages
  members, stores and access only; reading and editing memory could be studied
  later.
- Hosting Tiroir for several organisations: one server serves one organisation.
- Permissions per drawer: access is per store, so content with a different
  readership goes in a different store.
- Single sign-on with an outside identity provider.
- Hosts other than Claude: the connection is designed to allow them later.
- Writing to a store through Git: clones and mirrors are read-only.

The full list, and the reasons, are in the project's requirements on
[GitHub](https://github.com/ancelin-code/tiroir).
