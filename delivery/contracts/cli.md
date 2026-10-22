# Contract: command-line interface

**Status:** draft
**Parties:** `tiroir.cli` (provider); `tiroir.server` (the MCP endpoint the
member CLI calls), `tiroir.core` (the administration CLI), the documentation,
CI benchmarks, the evaluation harness and the deployment stack (ADR-016)
(consumers).

## Purpose

The terminal surfaces (U3): a **member CLI** for technical members, run on
their own machine against a server, and an **administration CLI**, run inside
the server's container. Both are one program, `tiroir`, from the same package.

## Shape

### Member CLI

`tiroir <command> [options]`, an MCP client of the server: each command is one
call of a tool in `mcp-tools.md`, and prints its result. Connection settings,
in order of precedence: `--server <url>` and `--token-env <VAR>` options, then
the `TIROIR_SERVER` and `TIROIR_TOKEN` environment variables, then
`~/.config/tiroir/cli.yaml` (`server`, and `token` only if the user chose to
store it there). The token is a personal access token with the `cli` scope
(ADR-015). Global options: `--json` (the tool's `structuredContent` on
stdout). Human output goes to stdout; diagnostics to stderr, never containing
memory content (Y5). Confirmations are interactive; `--yes` confirms without
asking and is refused for `purge` when stdin is not a terminal.

| Command | Tool | Purpose |
|---|---|---|
| `tiroir stores` | `tiroir_status` | Stores, audience, access, default, pending proposals. |
| `tiroir drawers [--store] [--type <t>]` | `tiroir_read` `drawers` | List drawers with their names. |
| `tiroir search <query> [--drawer <ref>]... [--all-drawers] [--type] [--kind] [--since] [--until] [--field k=v]... [--limit n]` | `tiroir_search` | Search (R1–R6); prints an abstention explicitly. |
| `tiroir read <ref> [--log] [--limit n]` | `tiroir_read` | Show a summary, a log or an entry. |
| `tiroir links <ref> [--drawer <ref>]... [--all-drawers]` | `tiroir_read` `links` | Outgoing and incoming links (L4). |
| `tiroir log <drawer ref> [<text> \| -]` | `tiroir_write` `log` | Append a log entry (proposal on team stores). |
| `tiroir proposals [list\|confirm <id>\|discard <id>]` | `tiroir_status`, `tiroir_confirm` | The member's pending and stale proposals. |
| `tiroir doctor [--store]` | `tiroir_store` `doctor` | Schema, metadata, sections, links, weak names, index freshness. |
| `tiroir eval --store <s> [--queries <file>]` | `tiroir_store` `eval` | Evaluation report (V1, V4). |
| `tiroir migrate --store <s> --schema <file> [--rename old=new]... [--apply]` | `tiroir_store` `migrate` | Dry run by default (I4); `--apply` asks to confirm. |
| `tiroir purge <drawer ref \| entry id \| shared path> [--apply]` | `tiroir_store` `purge` | Dry run by default (E1); `--apply` asks the user to type the drawer id. |

### Administration CLI

`tiroir admin <command> [options]`, run in the container
(`docker compose exec tiroir tiroir admin …`), calling `tiroir.core` directly
on `/data`. It needs no token: shell access to the container is the
administrator's credential. Changes to members and grants take effect at the
members' next request (A4).

| Command | Purpose |
|---|---|
| `tiroir admin init` | First start: create the first administrator and print a one-time sign-in link (ADR-016). |
| `tiroir admin members [list\|add <handle> --name <n> [--admin]\|disable <handle>\|reset-password <handle>]` | Members (A3). |
| `tiroir admin stores [list\|add <name> --audience personal\|team --language <code> [--owner <handle>]]` | Stores. A `personal` store needs `--owner`. |
| `tiroir admin grant <handle> <store> read\|write` / `tiroir admin revoke <handle> <store>` | Access (A2). |
| `tiroir admin embedding <store> [--model <id> \| --external <base-url> --external-model <name> --key-env <VAR>]` | Embedding choice per store (R4). |
| `tiroir admin mirrors <store> [list\|add <url>\|remove <id>]` | Mirrors (Y6); `add` over SSH prints the public key. |
| `tiroir admin index [--store] [--rebuild]` | Bring indexes up to date, or rebuild them (R7). |
| `tiroir admin eval --store <s> [--queries <file>] [--calibrate]` | Evaluation; `--calibrate` stores the threshold (V4, ADR-006). |
| `tiroir admin backup <file>` / `tiroir admin restore <file>` | A6, ADR-016. |
| `tiroir admin state` | Version, stores, index freshness, mirror lag, model status (A3). |
| `tiroir admin serve` | Run the server (the image's entry point, ADR-009). |

**Exit codes**, both CLIs: `0` success (including an abstaining search and a
dry run); `1` operation failed; `2` usage error; `3` refused by an invariant
or access rule (`access.read-only`, `drawer.purged`, `scope.denied`,
`link.unresolved`, `log.modified`); `4` confirmation declined; `5` store busy;
`6` authentication failed or server unreachable.

## Example

```text
$ export TIROIR_SERVER=https://memoire.cabinet.fr TIROIR_TOKEN=tir_…
$ tiroir search "échéance TVA" --drawer cabinet-exemple:clients/c042
cabinet-exemple:clients/c042  summary › Échéances  2026-10-02
  TVA mensuelle, déclaration le 19 du mois suivant.

$ docker compose exec tiroir tiroir admin grant bob cabinet-exemple read
bob: read access to cabinet-exemple
```

## Error cases

| Condition | Result |
|---|---|
| Unknown command or option | usage on stderr, exit 2 |
| No server or token configured (member CLI) | `error: cli.not-configured`, exit 6 |
| HTTP 401 from the server | `error: auth.failed`, exit 6 |
| Core or tool error | `error: <code>: <message>` on stderr, exit 1, 3 or 5 per the table above |
| `--json` with an error | `{"error": {"code": …, "message": …}}` on stdout, same exit code |

## Changing this contract

Lanes are building against this. A change needs agreement from every party
listed above, and the lanes must be told; a silent change produces work that
cannot be integrated.
