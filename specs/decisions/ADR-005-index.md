# ADR-005: Index each store in one SQLite file beside its repository, built from its commits

**Status:** accepted
**Date:** 2026-10-21, revised 2026-10-22 for the server

## Context

Search needs full-text and vector retrieval with metadata filters (R1), an
index that is derived and rebuildable (R7), and that serves only content the
user has confirmed. The server process reads it for every member, and the
administration CLI may read it too (ADR-009). The prior-art review found
brute-force vector search fast enough below about 50,000 chunks.

## Decision

- **Engine:** SQLite through Python's `sqlite3`, with FTS5; the image's SQLite
  build is checked for FTS5 at start and in CI.
  - Full text: an FTS5 table with two columns, one with language-normalised
    and stemmed tokens and one with raw identifier tokens (ADR-007).
  - Vectors: float32 arrays stored as BLOBs, one row per chunk and model,
    loaded once into the server process as NumPy arrays, per store and
    model, and searched by brute-force dot product.
  - Metadata, files, chunks, the detection names table (ADR-008) and the
    links table (ADR-014) are plain tables in the same file.
- **Location:** one file per store in the data directory,
  `<data>/index/<store-id>.sqlite`, never inside the store's repository
  (ADR-004).
- **Source:** the index reflects the tree of `main`'s head (ADR-010); there is
  no working copy.
- **Freshness:** the indexer (ADR-009) runs after every commit and at start: it
  compares the commit recorded in the index with the head and re-indexes the
  files that changed between them. Text, metadata, names and links are updated
  at once, so a write is visible to lexical search immediately (W4, P3);
  embeddings follow in the background, and until they land the new chunks are
  found by lexical search only.
- **Concurrency:** WAL mode; readers never block; the indexer is the only
  writer of a store's index.
- **Rebuild:** deleting the file and running `tiroir admin index --rebuild`
  produces the same results (R7). The file records the schema hash and the embedding
  model; a mismatch triggers a rebuild of the affected parts.

## Alternatives considered

- **SQLite with the sqlite-vec extension** - vector search in SQL, loadable
  from Python, but one more native dependency for no measurable gain
  at our size. Can replace the in-memory scan later behind the same index
  interface.
- **DuckDB (agentcairn's choice)** - good analytics engine, but a larger
  dependency, and its full-text extension is normally installed from DuckDB's
  extension repository at run time, which conflicts with the no-egress
  invariant.
- **Tantivy (`tantivy-py`)** - better full-text engine with French stemming
  built in, but a second store beside SQLite for metadata, names and vectors,
  and one more native dependency.
- **LanceDB or Chroma** - vector-first databases; heavy, and opaque compared
  with one SQLite file a user can inspect.
- **PostgreSQL with pgvector** - one database for the server state and every
  index, suited to a later hosted offering, but a second service to run and
  back up (ADR-004), for indexes that are derived and rebuildable.

## Consequences

The server holds every store's vectors in memory: about 1.5 KB per chunk at
384 dimensions and 4 KB at 1,024, so P6's store (about 62,000 chunks) takes
from 95 MB to 250 MB depending on the model chosen by ADR-006, counted against
P4. A NumPy scan of that many vectors takes milliseconds; sqlite-vec or an
approximate index is reconsidered only if the P2 or P4 benchmark says so.
Embeddings lag behind commits by the indexer's queue, which the
administration page and `doctor` report.
