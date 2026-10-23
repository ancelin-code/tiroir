-- Sign-in and OAuth (ADR-015): registered clients, authorization codes,
-- tokens and web sessions. Every secret is stored as its SHA-256 digest, never
-- in clear; clients registered by a metadata document (CIMD) are not stored.

CREATE TABLE oauth_clients (
    client_id TEXT PRIMARY KEY,
    metadata TEXT NOT NULL,  -- the registered client, as JSON, without secret
    secret_hash TEXT,
    created TEXT NOT NULL
);

CREATE TABLE oauth_codes (
    code_hash TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    member TEXT NOT NULL REFERENCES members (id),
    scopes TEXT NOT NULL,
    code_challenge TEXT NOT NULL,
    redirect_uri TEXT NOT NULL,
    redirect_uri_explicit INTEGER NOT NULL,
    resource TEXT,
    expires REAL NOT NULL
);

-- An access token and its refresh token share a grant, revoked together.
CREATE TABLE oauth_tokens (
    token_hash TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('access', 'refresh')),
    grant_id TEXT NOT NULL,
    client_id TEXT NOT NULL,
    member TEXT NOT NULL REFERENCES members (id),
    scopes TEXT NOT NULL,
    resource TEXT,
    expires INTEGER NOT NULL
);

CREATE INDEX oauth_tokens_grant ON oauth_tokens (grant_id);

CREATE TABLE web_sessions (
    session_hash TEXT PRIMARY KEY,
    member TEXT NOT NULL REFERENCES members (id),
    expires INTEGER NOT NULL
);
