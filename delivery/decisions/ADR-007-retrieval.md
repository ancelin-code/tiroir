# ADR-007: Chunk by section and entry, fuse lexical and vector ranks, and abstain on per-channel floors

**Status:** proposed
**Date:** 2026-10-21

## Context

Retrieval must find exact identifiers (R2), be insensitive to diacritics and
inflection in French (R3), combine lexical and semantic results (R1), beat
each channel alone on the bundled sets (V3) and return nothing rather than a
weak match (R5). These rules are shared by search, evaluation and calibration,
so they are fixed once.

## Decision

- **Chunks:** a summary yields one chunk per section; a log entry yields one
  chunk, split at paragraph boundaries above 400 tokens; a shared document
  yields one chunk per level-2 section. Each chunk carries its store, drawer,
  drawer type, kind, section, date and metadata for filtering.
- **Text normalisation**, applied identically to indexed text and queries:
  Unicode NFKC, case folding, diacritics removed, the store language's stop
  words dropped, Snowball stemming for that language (PyStemmer). Stored in
  the FTS5 `text` column with the `unicode61` tokenizer.
- **Identifier tokens:** tokens containing a digit, and runs of digits split
  by spaces, dots or dashes (`123 456 789`, `2026-001`), are also stored
  unstemmed and joined (`123456789`) in the FTS5 `ids` column.
- **Candidates:** up to 50 from FTS5 (BM25) and up to 50 from vector cosine,
  after the scope filter (X1) and the metadata filters, never before them.
- **Abstention floors**, applied per channel before fusion:
  - a lexical candidate is admitted if it matches an identifier token of the
    query exactly, or at least half of the query's content terms (minimum one);
  - a vector candidate is admitted if its cosine reaches the threshold
    calibrated for the model (ADR-006).
  No admitted candidate means an empty result, reported as an abstention.
- **Fusion:** Reciprocal Rank Fusion with k = 60 over the admitted candidates,
  then two rules: a candidate matching a query identifier exactly ranks first;
  the vector channel's best candidate is kept in the top 3 (Cairn's fusion
  guard). Across several stores, ranks are fused the same way.
- **No reranker** in v1.

## Alternatives considered

- **Score fusion (weighted BM25 + cosine)** - needs the two scales calibrated
  against each other per store and model; rank fusion does not.
- **A single composite score floor** (Cairn) - one threshold hides which
  channel failed; per-channel floors are calibrated separately and explain
  abstentions in the evaluation report.
- **A cross-encoder reranker** - measured gains in prior art are modest on
  short entries, and it adds a second model, latency and memory.
- **FTS5 `porter` tokenizer** - English only; French stemming has to be done
  before indexing.
- **Fixed-size chunks** - cut sections in the middle and break the
  section-level citation that injection and merging rely on.

## Consequences

The lexical half of retrieval needs no model, so it works in the hook and
before embeddings catch up (ADR-005). Stemming is per language: a store has one
memory language, and mixed-language content is matched lexically only on
exact forms. The floors and k are evaluation parameters, tuned on the bundled
sets and reported by V1, not hard-coded truths.
