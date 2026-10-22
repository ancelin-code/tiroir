# ADR-015: Authenticate members with a password on the server, act as the OAuth authorization server for MCP clients, and issue personal tokens for Git and the CLI

**Status:** proposed
**Date:** 2026-10-22

## Context

Members sign in to connect a host, and no credential is typed into a
conversation (A4). Claude Desktop, Claude on the web and mobile, and Claude
Code reach a remote MCP server through the MCP authorization flow: OAuth 2.1
with PKCE, the server advertising its authorization server, and clients
registering by Client ID Metadata Documents or, for older clients, Dynamic
Client Registration (MCP specification 2026-07-28). Read-only clones (Y7) and
the member CLI (U3) need a credential that works outside a host. Revoking
access takes effect at the member's next request (A4). Single sign-on with an
outside identity provider is out of scope.

## Decision

- **Member sign-in:** handle and password on tiroir's sign-in page; passwords
  hashed with Argon2id. The administrator sets an initial password, which the
  member must change at first sign-in. Repeated failures are throttled per
  handle and per address. Web sessions use a secure, HTTP-only, same-site
  cookie.
- **OAuth for MCP clients:** tiroir is its own authorization server, built on
  the MCP Python SDK's authorization support:
  - the MCP endpoint publishes Protected Resource Metadata pointing to tiroir,
    which publishes Authorization Server Metadata;
  - client registration by Client ID Metadata Documents
    (`client_id_metadata_document_supported: true`), fetching the client's
    public metadata document over HTTPS when it first connects, which the
    network invariant allows; and by Dynamic Client Registration for clients
    that still use it;
  - authorization code with PKCE (S256) only; the authorization step is the
    sign-in page followed by a consent page naming the client;
  - access tokens are opaque, stored hashed in `server.db`, valid one hour;
    refresh tokens rotate on use and expire after 30 days unused.
- **Checking a request:** every MCP and Git request resolves its token to a
  member and re-reads that member's status and grants from `server.db`; a
  disabled member or a revoked grant fails at once (A4, X1a). No access
  decision is carried inside a token.
- **Personal access tokens:** a member creates them on their account page, each
  with a name, an expiry (default 90 days) and a scope: `git:read` (clones,
  Y7) or `cli` (the member CLI, which speaks MCP with the token as a bearer
  token). Shown once, stored hashed, revocable from the account page or by
  the administrator.
- **Administration:** the administration page requires a web session of a
  member with the administrator flag, and asks for the password again before
  member and access changes.
- **Transport:** HTTPS only (A5), on the own-machine setup too (ADR-016).

## Alternatives considered

- **An outside identity provider in the stack** (Keycloak, Authentik) - mature
  OAuth and multi-factor sign-in, but a heavy second service with its own
  administration; tiroir keeps it possible later by staying a standard OAuth
  authorization server.
- **Static bearer tokens pasted into each host** - simple, but Claude Desktop,
  the web and mobile custom connectors expect the OAuth flow, and a pasted
  token is a credential handled by hand.
- **Signed self-contained tokens (JWT)** - no lookup per request, but revocation
  would wait for expiry, against A4.
- **Magic links by email** - no password, but the server would need to send
  mail, which the network invariant does not list and many self-hosted
  setups cannot do.

## Consequences

tiroir holds credentials, so its sign-in and OAuth code are security-critical:
the first milestone tests them against the three Claude hosts and with an
OAuth conformance checklist, and the code uses the SDK's and libraries'
implementations rather than tiroir's own where they exist. Multi-factor
sign-in is not in v1; the documentation recommends strong passwords and
limiting the server's exposure. Every request costs one database read of the
member's grants, negligible next to P1 and P2.
