# ADR-005: Index each store in one SQLite file outside the store, built from the committed state

**Status:** proposed
**Date:** 2026-10-21

## Context

Search needs full-text and vector retrieval with metadata filters (R1), an
index that is derived and rebuildable (R7), and that serves only content the
user has confirmed (Y9). Three kinds of process read it concurrently: the MCP
server, the per-prompt hook and the CLI (ADR-009). The prior-art review found
brute-force vector search fast enough below about 50,000 chunks.

## Decision

- **Engine:** SQLite through Python's standard `sqlite3` module.
  - Full text: an FTS5 table with two columns, one with language-normalised
    and stemmed tokens and one with raw identifier tokens (ADR-007).
  - Vectors: float32 arrays stored as BLOBs, one row per chunk and model,
    searched by brute force with numpy in the reading process.
  - Metadata, files, chunks and the detection names table (ADR-008) are plain
    tables in the same file.
- **Location:** one file per store in the data directory
  (`<data>/stores/<store-id>/index.sqlite`), never inside the store.
- **Source:** the index reflects the tree of the store's last commit, not the
  working copy. Outside edits (Y9) are invisible to search until confirmed and
  committed.
- **Freshness:** every process, before reading, compares the commit recorded
  in the index with the store's current commit and re-indexes the files that
  changed between them. Text, metadata and names are updated immediately;
  embeddings are computed only by processes that have the model loaded (MCP
  server, CLI). Until then, the new chunks are found by lexical search only.
- **Concurrency:** WAL mode; readers never block; one writer at a time per
  store, serialised by the store lock (ADR-010).
- **Rebuild:** deleting the file and running `tiroir index --rebuild` produces
  the same results (R7). The file records the schema hash and the embedding
  model; a mismatch triggers a rebuild of the affected parts.

## Alternatives considered

- **SQLite with the sqlite-vec extension** - vector search in SQL, but it
  needs `enable_load_extension`, which some Python builds lack, and adds a
  native extension for no measurable gain at our size. Can replace the numpy
  scan later behind the same index interface.
- **DuckDB (agentcairn's choice)** - good analytics engine, but a larger
  dependency, and its full-text extension is normally installed from DuckDB's
  extension repository at run time, which conflicts with the no-egress
  invariant.
- **Tantivy (`tantivy-py`)** - better full-text engine with French stemming
  built in, but a second store beside SQLite for metadata, names and vectors,
  and one more native dependency.
- **LanceDB or Chroma** - vector-first databases; heavy, and opaque compared
  with one SQLite file a user can inspect.
- **Indexing the working copy** - simpler, but would serve unconfirmed outside
  edits, against Y9.

## Consequences

A process holds every vector of the stores in use in memory while searching:
about 15 MB per 10,000 chunks at 384 dimensions, within P4. Past roughly
50,000 chunks per store the scan nears the P2 budget, the point at which
sqlite-vec or an ANN index is reconsidered. Embeddings lag behind commits
until an MCP server or CLI process runs, which `doctor` reports.
