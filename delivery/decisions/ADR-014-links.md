# ADR-014: Link files with Obsidian wikilinks and detected mentions, indexed but never followed

**Status:** proposed
**Date:** 2026-10-21

## Context

Log entries, summaries and shared documents refer to each other: an entry
about one client cites a procedure, another client's similar case, or an
earlier entry (L1–L6). Obsidian users expect `[[…]]` links and a store that
works as a vault (S5, H3). Three rules already in place constrain links: a
scoped read never returns another drawer's content (X1), log entries are never
modified (W1), and a purge must erase a drawer's name from the whole history
(E1, ADR-011). Drawer paths contain client codes and names, so a link is
itself sensitive data.

## Decision

- **Two kinds of link, one index.**
  - **Explicit:** a wikilink `[[<path>]]`, the path relative to the store root
    without `.md`, optionally followed by `#<heading>` and `|<label>`. A link
    to a drawer targets its summary (`[[clients/c042/summary]]`); a link to an
    entry names its file (`[[clients/c042/log/2026/10/2026-10-21T143205Z-alice-k3f9]]`).
    These are the paths Obsidian resolves when the store is opened as a vault.
    Links inside code spans and code blocks are ignored. Markdown links
    (`[text](path.md)`) are not links for tiroir in v1.
  - **Mention:** a drawer name declared under `detect.names` found in a file's
    text, by the matcher of ADR-008. Mentions of the file's own drawer and
    ambiguous names (C2) are not recorded. Mentions need no syntax, so a store
    written without a single `[[…]]` still has its links.
- **Writes check explicit links:** a write whose text holds an explicit link
  that resolves to no file of the same store is refused with
  `link.unresolved`, naming the link. A log entry can never be corrected
  later, so a broken link must not get in. `doctor` reports any broken link
  that remains, for example after a restore from an older backup.
- **Same store only.** A link resolves in its own store; a reference to another
  store is plain text. Stores have different members (M1), so a cross-store
  link would show one store's names to people without access to the other.
- **Index:** a `links` table in the index (ADR-005): source file and section,
  kind, raw target, resolved target (empty when unresolved) and, for
  mentions, the text that matched. Derived and rebuilt with the rest (R7).
  Explicit links and mentions are updated with the file's text by any process
  by the indexer (ADR-009). When the names table changes (a drawer created,
  an alias added), the indexer re-runs the matcher over every chunk of the
  store in the background.
- **Reading links:** `tiroir_read` with `what: links` (and `Core.links`,
  `tiroir links`) returns a file's or a drawer's outgoing and incoming links,
  each with its kind and matched text, never the other end's content. In a
  scoped request, only links whose other end lies in the active drawers or the
  shared space are returned; the others need the explicit cross-drawer request
  (`all_drawers`, X2), and their count is not disclosed either (X1).
- **Links are never followed** by search, reading or injection: reading an
  entry returns its text, links included, and nothing from their targets.
  Search ranking ignores links in v1.
- **Moves:** a migration that changes drawer paths (I4) appends each move to
  `.tiroir/moves.yaml` (old path, new path, date) and rewrites explicit links
  in summaries and shared documents, as part of its dry run. Log entries keep
  their old paths; tiroir resolves them through the chain of moves.
- **Purge:** besides removing the purged files, the history rewrite of ADR-011
  replaces every explicit link to a purged path, in every other file and every
  commit, with the text `[purged]`, and drops the moves involving purged
  paths. The previous blob ids of the files it changed join the purge record,
  so the push guard refuses them too (E2, E5). Mentions are plain text and are
  not changed: the dry run lists the files that mention the purged drawer's
  names, so the user can purge those entries as well.

## Alternatives considered

- **Mentions only** - no syntax and no broken links, but cannot point at one
  entry or a shared document, and cannot express a link the user wants that
  no declared name covers.
- **Explicit links only** - the user or agent must write every link; the many
  existing references by name stay invisible.
- **Markdown links** (`[text](clients/c042/summary.md)`) - more portable, but
  Obsidian's graph and the Agent Memory Repo format (H3) use wikilinks, and
  two syntaxes double the parsing and the purge masking.
- **Stable identifiers** (`[[id:…]]` from a UUID in each frontmatter) - survive
  moves without a move record, but neither Obsidian nor a human can follow
  them.
- **Obsidian short names** (`[[c042]]`, resolved by file name) - every drawer's
  summary is called `summary.md`, so short names are ambiguous.
- **Leaving links untouched by a purge** - simpler, but keeps the purged
  drawer's path, often its client code, in other drawers' history, which is
  what ADR-011 avoids by hashing paths in the purge record.

## Consequences

A purge now changes files outside the purged drawer, in history too, which
makes it slower and touches more commits; it is the one exception to "log
entries are never modified" (E4, E5), and its dry run shows every such file.
After a move, links in old log entries no longer open in Obsidian, though
tiroir still resolves them. Mentions are only as good as the declared names:
a weak name (ADR-008) produces noisy mentions, which `doctor` already flags.
Re-matching every chunk when names change costs a few seconds at the P6
scale and runs in the background. A graph view can later be drawn from the
`links` table without any format change.
