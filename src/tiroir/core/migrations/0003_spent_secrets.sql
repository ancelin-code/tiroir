-- Reuse detection (OAuth 2.1): the digests of the authorization codes and
-- refresh tokens already exchanged, with the grant they led to. Presenting one
-- again deletes that grant. A row goes with its grant, or when it expires.

CREATE TABLE oauth_spent_secrets (
    secret_hash TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('code', 'refresh')),
    grant_id TEXT NOT NULL,
    expires INTEGER NOT NULL
);

CREATE INDEX oauth_spent_secrets_grant ON oauth_spent_secrets (grant_id);
