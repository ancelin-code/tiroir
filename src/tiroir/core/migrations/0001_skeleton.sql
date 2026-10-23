-- The server database's first schema: members, stores and the access they
-- grant (ADR-004). Applied inside a transaction that also records the version.

CREATE TABLE members (
    id TEXT PRIMARY KEY,
    handle TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    is_admin INTEGER NOT NULL DEFAULT 0,
    must_change_password INTEGER NOT NULL DEFAULT 0,
    created TEXT NOT NULL,
    disabled TEXT
);

CREATE TABLE stores (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    audience TEXT NOT NULL CHECK (audience IN ('personal', 'team')),
    language TEXT NOT NULL,
    created TEXT NOT NULL
);

CREATE TABLE grants (
    member TEXT NOT NULL REFERENCES members (id),
    store_id TEXT NOT NULL REFERENCES stores (id),
    access TEXT NOT NULL CHECK (access IN ('read', 'write')),
    PRIMARY KEY (member, store_id)
);
