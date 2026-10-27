-- The member's default store for writes (M4): at most one per member, and only
-- a store the member holds a grant on counts.

CREATE TABLE default_stores (
    member TEXT PRIMARY KEY REFERENCES members (id),
    store_id TEXT NOT NULL REFERENCES stores (id)
);
