# Contract: HTTP routes of the server

**Status:** draft
**Parties:** `tiroir.server` (provider: MCP, OAuth, account and administration
pages, Git, health); the Claude hosts and the Claude Code plugin, the member
CLI, Git clients, the deployment stack (Caddy, health checks) (consumers).

## Purpose

Fixes every path the server answers, who may call it and with what
credential, so the lanes building MCP, authentication, pages, Git and
deployment share one map and one set of access rules (ADR-009, ADR-010,
ADR-015, ADR-016).

## Shape

One Starlette application on port 8080 inside the container, behind Caddy,
which terminates HTTPS (A5). Paths are relative to the server's origin, for
example `https://memoire.cabinet.fr`.

| Path | Methods | Credential | Purpose |
|---|---|---|---|
| `/mcp` | `POST`, `GET`, `DELETE` | OAuth access token, or personal token with scope `cli` | MCP streamable HTTP endpoint (`mcp-tools.md`). |
| `/.well-known/oauth-protected-resource` | `GET` | none | Protected Resource Metadata (RFC 9728) for `/mcp`. |
| `/.well-known/oauth-authorization-server` | `GET` | none | Authorization Server Metadata (RFC 8414), with `client_id_metadata_document_supported: true`. |
| `/oauth/authorize` | `GET`, `POST` | web session (redirects to `/signin`) | Authorization endpoint: consent page naming the client, PKCE S256 required. |
| `/oauth/token` | `POST` | client authentication per its metadata | Token endpoint: authorization code and refresh token grants. |
| `/oauth/register` | `POST` | none | Dynamic Client Registration (RFC 7591), for clients without CIMD. |
| `/oauth/revoke` | `POST` | client authentication | Token revocation (RFC 7009). |
| `/signin`, `/signout` | `GET`, `POST` | none / web session | Sign-in page (handle, password), password change at first sign-in. |
| `/account` | `GET`, `POST` | web session | The member's page: stores and access, personal access tokens (create, revoke), memory skill archive download and freshness (ADR-013), password change. No memory content. |
| `/account/skill.zip` | `GET` | web session | The member's memory skill archive. |
| `/admin` and `/admin/...` | `GET`, `POST` | web session of an administrator; password re-entry for member and access changes | Administration page (A3): members, stores, grants, embedding per store, mirrors, server state. No memory content. |
| `/git/<store-name>.git/info/refs`, `/git/<store-name>.git/git-upload-pack` | `GET`, `POST` | HTTP basic auth: handle and a personal token with scope `git:read`, on a store the member is granted | Read-only clone and fetch (Y7). |
| `/git/<store-name>.git/git-receive-pack` | any | any | Always `403`: pushes are refused. |
| `/health` | `GET` | none | `200` with `{"status": "ready"\|"starting", "version": …}`; `503` while not ready. No store names. |

Rules for every route:

- Responses never contain memory content outside `/mcp` and `/git` (A3, Y5).
- A store a member is not granted answers exactly like a store that does not
  exist (`404` on `/git`, `store.unknown` on `/mcp`) (X1a).
- Web forms use same-site cookies and a CSRF token; pages set a strict
  Content-Security-Policy and load no third-party resources.
- Request logs record method, path template, status, duration and member
  handle, never query strings or bodies (Y5).

## Example

```text
POST /mcp HTTP/1.1
Host: memoire.cabinet.fr
Authorization: Bearer tir_at_9b2…
Content-Type: application/json
Accept: application/json, text/event-stream

{"jsonrpc":"2.0","id":7,"method":"tools/call",
 "params":{"name":"tiroir_search","arguments":{"query":"échéance TVA"}}}
```

```text
$ git clone https://alice@memoire.cabinet.fr/git/cabinet-exemple.git
Password for 'https://alice@memoire.cabinet.fr': <personal token, scope git:read>
```

## Error cases

| Condition | Result |
|---|---|
| No or invalid token on `/mcp` | `401` with `WWW-Authenticate: Bearer resource_metadata="…/.well-known/oauth-protected-resource"` |
| Token valid but member disabled | `401`, same header |
| Page without a web session | `303` to `/signin?next=…` |
| `/admin` by a non-administrator | `403` |
| `/git/...` with a token lacking `git:read`, or a store not granted | `404` |
| Any push | `403` |
| Server starting (migrations, model loading not required) | `/health` `503`; other routes `503` with `Retry-After` until migrations end |

## Changing this contract

Lanes are building against this. A change needs agreement from every party
listed above, and the lanes must be told; a silent change produces work that
cannot be integrated.
