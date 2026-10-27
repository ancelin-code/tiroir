# Skeleton exit check

The checklist of the skeleton milestone's exit criterion
([decomposition](../../delivery/decomposition.md#skeleton)), to run once on a
real VPS with the project owner. Each step says what to record; put the record
in the milestone review.

> On a VPS with a domain name, `docker compose up -d` and `tiroir admin init`
> give a server answering over HTTPS; the administrator creates a personal
> store from the `accounting-firm` preset; in Claude Desktop, after adding the
> server as a custom connector and signing in, the member appends a log entry
> to a client's drawer and finds it with a keyword search within 2 seconds; the
> entry is one commit, with tiroir's trailers, in the store's history.

Follow [Install tiroir on a VPS](../install/vps.md) and
[Connect Claude Desktop](../connect/claude-desktop.md); this page adds only
what to observe.

| # | Step | Clause of the criterion | Record |
|---|---|---|---|
| 1 | Prepare the VPS and the domain (guide, prerequisites). | a VPS with a domain name | Provider, architecture, operating system, Docker and Compose versions, domain name. |
| 2 | `docker compose up -d` (guide, step 3). | `docker compose up -d` | Image tag and digest (`docker compose images`), time from the command to a healthy `docker compose ps`. |
| 3 | `curl https://<domain>/health` from another machine, without `--insecure`. | a server answering over HTTPS | The response body (`status`, `version`), the certificate issuer shown by `curl -v`, time to obtain the certificate on first start. |
| 4 | `docker compose exec tiroir tiroir admin init`, then change the password at the first sign-in at `https://<domain>/signin`. | `tiroir admin init` | That an administrator exists and could sign in. Do not record the password. |
| 5 | Create a member and a personal store from the preset (guide, steps 5 and 6). | the administrator creates a personal store from the `accounting-firm` preset | The commands run, the output of `tiroir admin stores list`, the store's id from `ls /data/stores`. |
| 6 | Add the connector in Claude Desktop and sign in (connector guide, steps 1 and 2). | after adding the server as a custom connector and signing in | Claude Desktop version and platform; every field the dialog showed against what the guide says; what the sign-in and consent pages looked like against the guide; anything that failed or needed a retry. |
| 7 | Ask Claude to append a log entry to a client's drawer (connector guide, step 4). | the member appends a log entry to a client's drawer | The drawer used, the tool Claude called, and whether it asked for any confirmation. |
| 8 | Ask Claude to find the entry by a keyword it contains (connector guide, step 3). | finds it with a keyword search within 2 seconds | Whether the entry was found, and the time from sending the request to the hits shown (stopwatch, three tries). The 2 seconds are for the search itself; note the model's own time apart if it dominates. |
| 9 | `docker compose exec tiroir git -C /data/stores/<id>.git log -1 --format=fuller`. | the entry is one commit, with tiroir's trailers, in the store's history | The commit as printed: that it is the latest and only commit for the entry, and carries the `Tiroir-Op`, `Tiroir-Drawer`, `Tiroir-Author` and `Tiroir-Via` trailers. Check that the entry's file is the only one it changes (`git show --stat`). |

## Checks against the Claude hosts

[ADR-013](../../delivery/decisions/ADR-013-adapters-and-skills.md) and
[ADR-015](../../delivery/decisions/ADR-015-authentication.md) leave checks to
make with a real Claude host. Record the result of each at step 6:

- Which way the application identified itself to the server: by a client
  metadata document or by dynamic registration (`/oauth/register`). The
  consent page shows the application's identifier.
- That the connection needed no pre-registered client ID or secret.
- That the connector worked with the streamed responses of `/mcp` through
  Caddy, without buffering.
- Whether Claude Desktop asked for confirmation before the log write, and
  whether it declared the elicitation capability (ADR-012).
- Whether the connection survived a restart of Claude Desktop (token refresh).

## Verdict

The milestone passes when steps 1 to 9 all hold. Record the date, the people
present, and for any step that failed, what was changed to make it pass.
