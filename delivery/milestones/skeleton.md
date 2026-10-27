# Milestone review: skeleton

**Status:** draft
**Approved by:**

## Exit criterion

> On a VPS with a domain name, `docker compose up -d` and `tiroir admin init`
> give a server answering over HTTPS; the administrator creates a personal
> store from the `accounting-firm` preset; in Claude Desktop, after adding the
> server as a custom connector and signing in, the member appends a log entry
> to a client's drawer and finds it with a keyword search within 2 seconds; the
> entry is one commit, with tiroir's trailers, in the store's history.

**Held**, on 2026-10-27, run by the project owner (Ancelin Serre) following
[the exit checklist](../../docs/milestones/skeleton-exit-check.md) and the
guides as merged in #23, from a fresh clone of `develop`.

| # | Step | Observed |
|---|---|---|
| 1 | VPS and domain | Oracle Cloud free tier, `aarch64`, Ubuntu 24.04.4, Docker 29.6.2, Compose 5.3.1. Domain `141-253-104-33.sslip.io` (sslip.io resolves the name to the IP; no domain was bought). A previous Caddy and Forgejo were stopped first to free ports 80 and 443. |
| 2 | `docker compose up -d --build` | Image built on the VPS in 37.6 s (`linux/arm64`, image id `bd2f9d2d2de4`, 445 MB); both containers up, `tiroir` healthy, about 3 minutes from the command, clone and `.env` included. |
| 3 | HTTPS | `curl https://<domain>/health` from another machine (Oracle Cloud Shell), without `--insecure`: `{"status":"ready","version":"0.1.0"}`, certificate issued by Let's Encrypt (`YE2`) at first start. |
| 4 | `tiroir admin init` | Administrator `admin` created with an initial password. The administrator's first sign-in at `/signin` was not exercised; the member's first sign-in (step 6) went through the same pages. |
| 5 | Member and store | `admin members add ancelin`, then `admin stores add ancelin-memory --audience personal --language fr --owner ancelin --preset accounting-firm`; `stores list` printed `ancelin-memory  personal  fr  1 members`; store id `8990211a-4e6c-49a5-8d64-5842901ec457`. |
| 6 | Connector and sign-in | Claude Desktop 3.6556.2 on Windows, French interface, Pro plan. Connector added with the name and `https://<domain>/mcp`; sign-in, forced password change, consent, connected on the first try. |
| 7 | Log entry | Claude called `tiroir_write` with `action: log`, drawer `ancelin-memory:clients/c001`, after two read-only tool calls to locate the client. The only confirmation was Claude Desktop's own tool approval; tiroir asked none, as expected for a log entry in a personal store. |
| 8 | Keyword search | Three tries of "relance TVA": the new entry was found every time. End to end in Claude Desktop 8 to 10 s, dominated by the model. On the server, the same search (`search_lexical`, all drawers) took 2.5, 3.3 and 2.7 ms, the entry ranked first (`clients/c001`, `LOG`). |
| 9 | Commit | `HEAD` of `main` is `efbf70d`, author `Ancelin <ancelin@tiroir.invalid>`, message `tiroir: log-append clients/c001` with `Tiroir-Op: log-append`, `Tiroir-Drawer: clients/c001`, `Tiroir-Author: ancelin`, `Tiroir-Via: mcp`, and no memory content; it adds only `clients/c001/log/2026/10/2026-10-27T152447Z-ancelin-v98k.md`. |

Checks against the Claude hosts (ADR-013, ADR-015):

- **Client identification:** a client metadata document. The tokens carry
  `client_id` `https://claude.ai/oauth/mcp-oauth-client-metadata`, and
  `oauth_clients` is empty: dynamic registration was not used.
- **No pre-registered client:** the dialog has no OAuth fields at all.
- **Streaming through Caddy:** every tool call worked through Caddy with
  `flush_interval -1`.
- **Elicitation:** not observed. Whether Claude Desktop declares the
  capability was not checked; it matters from the team milestone, where
  writes need confirmation (ADR-012).
- **Restart:** the connector stayed connected after Claude Desktop was quit
  and restarted, and a search worked. Whether a token refresh happened (the
  restart may have been within the access token's lifetime) was not checked.

## Coverage

`coverage.sh --milestone skeleton`: covered 8 (A5, S1, S2, R3, R6, W1, Y2,
D3), partly 17, planned 0, not started 0.

Every partly covered requirement is partial by plan, with the remainder
assigned to a later milestone in its task's `Covers` note:

- **retrieval:** R1 (semantic retrieval and fusion), R2 (the judged
  evaluation set), R7 (rest of the index work), S4 (the `developer` preset
  and both judged query sets), D1 (adapter checks on macOS and Windows with
  the plugin).
- **team:** A2 (per-store access checks, the isolation property test), A4
  (grant revocation), M1 (several stores per member exercised), M3 (injected
  context and confirmations), S6, W4 (embeddings follow), Y1, U1 (the other
  tools and actions), U4 (web, mobile, full member documentation), U5 (the
  core's content).
- **operations:** A1 (own-machine setups), A4 (personal access tokens), Y1
  (mirrors and clones), Y5 (the remaining surfaces).

## What we learned

- **The architecture holds end to end on modest hardware.** Remote MCP with
  OAuth, Git stores and lexical search work from Claude Desktop on a free ARM
  VPS. Search is about 3 ms on the server; the 2-second budget is spent by
  the model, not by tiroir.
- **Claude identifies itself by a client metadata document**
  (`https://claude.ai/oauth/mcp-oauth-client-metadata`). ADR-015's open
  question is settled: this is the path to keep tested; dynamic registration
  is the fallback for other clients.
- **Claude Desktop classifies tiroir's tools correctly** from their
  annotations: `read`, `search` and `status` as read-only, `write` as
  write/delete, each needing the user's approval by default.
- **No tiroir image is published before the first `v*` tag**, so the guide
  built from source; fixed in #23 before merge. Publishing a release is now a
  prerequisite of a pull-based install.
- **The connector guide was written from memory and is wrong in places:**
  the path is Settings → Connectors → **+ Add** → "Add custom connector"; the
  dialog shows only **Name** and **Remote MCP server URL**, with no OAuth or
  advanced fields; the button is **Continue**, not **Add**; tool approvals
  should be mentioned. Fix it before the guides are used again.
- **Real-use retrieval signal:** "relance TVA" returned 10 hits, the right
  one first and 9 summaries that share "relanc" and "TVA" in unrelated
  sentences. The "half the content terms" floor admits them; this is the
  concrete case for the floor question the retrieval milestone carries (#20).
- **`vectors-pending` reads as "indexing in progress".** Claude told the user
  semantic search was being built. While no vector channel exists, the
  degradation should say "semantic search unavailable", not "pending".
- **A corporate TLS-intercepting proxy (Zscaler) prevents building the image**
  on a developer machine: uv and Python 3.13 reject its certificate. Not a
  tiroir defect, but the installation guide could mention it.
- **Storing each store in Git was re-examined against prior art and kept**
  (2026-10-27); the operations milestone measures purge and growth costs
  (#24).

## Decision

**Decision:** continue

The exit criterion held; nothing found requires revising the requirements or a
decision record before the retrieval milestone is cut. ADR-015 gains its
answer on client identification as an amendment, which does not change the
decision.

## Carried over

Into the retrieval cut:

- The four retrieval questions noted on the milestone (#20): French stemmer,
  fusion method and k, the lexical floor (with the "relance TVA" case above),
  and bounding identifier digit joins.
- Report the missing vector channel as unavailable rather than pending.
- Fix `docs/connect/claude-desktop.md` with the observed dialog (path, two
  fields, **Continue**, tool approvals).
- The start-time and CI check that SQLite has FTS5 (ADR-005), deferred by
  `search-001`.
- Check whether Claude Desktop declares the elicitation capability, and
  whether a token refresh happens after the access token expires.

Deferred from reviews of this milestone, for the milestone that owns the code:

- A shared lock between the indexer and `tiroir admin index --rebuild`, so an
  older diff is never applied over a newer index (`search-001`).
- The date filter excludes summaries and shared documents, which have no
  date (`search-001`).
- A rebuild reads every blob, attachments included, before classifying it
  (`search-001`).
- Store identifiers outside the quoted reference-data block in MCP results
  (drawer ids, types, paths, authors) (`server-004`, C4).
- The README's "design phase, nothing is usable yet" status line is stale.
- Publish a first release (`v0.1.0`) so the install can pull the image.
- Amend ADR-015 with the observed client identification.
