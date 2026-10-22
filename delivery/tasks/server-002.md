---
id: server-002
title: Sign members in and act as the OAuth authorization server
type: feat
epic: server
depends_on: [server-001]
parallel: true
conflicts_with: [server-001, server-003, server-004]
tier: plan
review: [security]
---

## Context

Claude Desktop, the web, mobile and Claude Code reach a remote MCP server
through the MCP authorization flow: OAuth 2.1 with PKCE, Protected Resource
and Authorization Server metadata, client registration by Client ID Metadata
Documents or Dynamic Client Registration
([ADR-015](../decisions/ADR-015-authentication.md)). tiroir is its own
authorization server, built on the MCP Python SDK's authorization support,
with members signing in by handle and password. The routes and their errors
are fixed by the [HTTP routes contract](../contracts/http-routes.md). This is
security-critical code: use the SDK's and libraries' implementations wherever
they exist.

## Covers

- A4 (part): sign-in with handle and password, the OAuth flow for MCP clients,
  token checks that re-read the member's status on every request so a
  disabled member fails at once; grant revocation and personal access tokens
  come in the team and operations milestones

## Scope

Files this task is expected to touch:

- `src/tiroir/server/auth/oauth.py`: the authorization server provider for the
  MCP SDK: Authorization Server Metadata with
  `client_id_metadata_document_supported: true`, CIMD fetching (HTTPS only,
  size and time limits, cached), Dynamic Client Registration, authorization
  code with PKCE S256 only, token and revocation endpoints, refresh token
  rotation; opaque tokens stored hashed in `server.db` (access one hour,
  refresh 30 days unused)
- `src/tiroir/server/auth/sessions.py`: web sessions (secure, HTTP-only,
  same-site cookie), CSRF tokens, sign-in throttling per handle and per address
- `src/tiroir/server/auth/pages.py` and `src/tiroir/server/templates/`
  (`signin.html`, `change_password.html`, `consent.html`): plain HTML, no
  third-party resources, strict Content-Security-Policy
- `src/tiroir/server/auth/verify.py`: `member_for_token(token) -> member` used
  by `/mcp`, returning the member only if active
- `src/tiroir/core/serverdb.py`: add the OAuth clients, codes, tokens and
  sessions tables as a new schema migration
- `src/tiroir/server/app.py`: mount `/.well-known/*`, `/oauth/*`, `/signin`,
  `/signout`
- `tests/server/test_oauth_flow.py`, `tests/server/test_signin.py`,
  `tests/server/test_cimd.py`

Out of scope:

- the `/mcp` endpoint itself (`server-004`), which uses `verify.py`
- personal access tokens and the account page (team and operations
  milestones), the administration page (team milestone)
- multi-factor sign-in, single sign-on (out of scope for v1)

## Acceptance criteria

- An automated test plays a full client: discovers the Protected Resource
  Metadata from a `401` on a protected test route, reads the Authorization
  Server Metadata, registers through a CIMD URL served by the test (and, in a
  second test, through DCR), signs in, consents, exchanges the code with the
  PKCE verifier, calls the protected route with the access token, refreshes
  it, and sees the old refresh token rejected.
- A code exchange without the right PKCE verifier, a `plain` challenge, a
  redirect URI not in the client's metadata, or an expired code is refused.
- After `tiroir admin members disable alice`, a request with Alice's still
  unexpired access token is refused with `401`.
- First sign-in with an initial password forces a password change.
- Ten failed sign-ins for one handle within a minute are throttled.
- Tokens and passwords never appear in logs or in `server.db` in clear.
- `mise run check` passes.

## Validation

`mise run test -- tests/server/test_oauth_flow.py tests/server/test_signin.py
tests/server/test_cimd.py`, then `mise run check`. The real check against
Claude Desktop happens in `deploy-002`.
