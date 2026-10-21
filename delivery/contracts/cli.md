# Contract: command-line interface

**Status:** draft
**Parties:** `tiroir-cli` (provider); the Claude Code plugin and the `.mcpb`
bundle (which run `tiroir mcp` and `tiroir hook`), the documentation, CI
benchmarks and the evaluation harness (consumers).

## Purpose

The terminal surface (U3) and the entry points hosts execute. Every command is
a thin layer over the core API (`core-api.md`).

## Shape

`tiroir <command> [options]`. Global options: `--store <name>` (default: all
stores, or the default store for writes), `--json` (machine-readable output on
stdout, matching the core result types), `--config <path>`. Human output goes
to stdout; diagnostics to stderr, never containing memory content (Y5).
Confirmation prompts are interactive; `--yes` confirms without asking and is
refused when stdin is not a terminal for `purge`.

| Command | Purpose |
|---|---|
| `tiroir init <path> --preset <name> --name <store> --audience personal\|team [--remote <url>]` | Create a store from a preset or `--schema <file>`; shows the plan, asks to confirm. |
| `tiroir store list` | Stores in use, audience, default, sync state. |
| `tiroir store connect <remote> [--path <dir>]` | SSH remote: generate the deploy key, print the public key and host steps. HTTPS remote: print the host's token page and permissions, then read the token without echo. Then wait for access, clone, register. |
| `tiroir store remove <name>` | Stop using a store on this machine (asks whether to delete the local copy and key). |
| `tiroir store default <name>` | Set the default store for writes (M4). |
| `tiroir drawers [--type <t>]` | List drawers with their names. |
| `tiroir search <query> [--drawer <ref>]... [--all-drawers] [--type] [--kind] [--since] [--until] [--field k=v]... [--limit n]` | Search (R1–R6); prints an abstention explicitly. |
| `tiroir read <ref> [--log] [--limit n]` | Show a summary, a log or an entry. |
| `tiroir links <ref> [--drawer <ref>]... [--all-drawers]` | Outgoing and incoming links of a drawer or file, with kind and matched text (L4). |
| `tiroir log <drawer ref> [<text> \| -]` | Append a log entry (proposal on team stores). |
| `tiroir proposals [list\|show <id>\|confirm <id>\|discard <id>]` | Pending, stale and outside-edit proposals. |
| `tiroir sync` | Sync now; prints the sync report. |
| `tiroir index [--rebuild]` | Bring indexes up to date, or rebuild them (R7). |
| `tiroir doctor` | Validate configuration, schemas, metadata, sections, links, weak names, model, index freshness, keys, remotes, skill freshness. |
| `tiroir migrate --schema <file> [--rename old=new]... [--apply]` | Dry run by default (I4); `--apply` asks to confirm. |
| `tiroir purge <drawer ref \| entry id \| shared path> [--apply]` | Dry run by default (E1); `--apply` asks the user to type the drawer id. |
| `tiroir eval [--queries <file>] [--calibrate]` | Evaluation report (V1); `--calibrate` stores the thresholds (ADR-006). |
| `tiroir install claude-code\|claude-desktop [--dry-run]` | Install or check the integration and write the memory skill (ADR-013). |
| `tiroir skill` | Regenerate the memory skill files. |
| `tiroir mcp` | Run the MCP server on stdio (used by hosts). |
| `tiroir hook claude-code user-prompt-submit` | Hook entry point (`claude-code-hook.md`). |

**Exit codes:** `0` success (including an abstaining search and a dry run);
`1` operation failed; `2` usage error; `3` refused by an invariant or a purge
record (`log.modified`, `drawer.purged`, `scope.denied`, `link.unresolved`); `4` confirmation
declined; `5` store busy.

## Example

```text
$ tiroir search "échéance TVA" --drawer cabinet-exemple:clients/c042
cabinet-exemple:clients/c042  summary › Échéances  2026-10-02
  TVA mensuelle, déclaration le 19 du mois suivant.

$ tiroir search "tarte aux pommes"
No result clears the confidence threshold (abstained).
```

## Error cases

| Condition | Result |
|---|---|
| Unknown command or option | usage on stderr, exit 2 |
| Core error | `error: <code>: <message>` on stderr, exit 1, 3 or 5 per the table above |
| `--json` with an error | `{"error": {"code": …, "message": …}}` on stdout, same exit code |

## Changing this contract

Lanes are building against this. A change needs agreement from every party
listed above, and the lanes must be told; a silent change produces work that
cannot be integrated. `tiroir mcp` and `tiroir hook …` are executed by
installed integrations: renaming them breaks existing installs.
