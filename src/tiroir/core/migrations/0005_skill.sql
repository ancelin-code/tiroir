-- The fingerprint of the memory skill each member last downloaded (ADR-013):
-- the skill is stale once their grants or a granted store's schema no longer
-- give the same fingerprint.

CREATE TABLE skill_downloads (
    member TEXT PRIMARY KEY REFERENCES members (id),
    fingerprint TEXT NOT NULL,
    downloaded TEXT NOT NULL
);
