# ADR-006: Embed locally with fastembed-rs, defaulting to multilingual MiniLM, with per-model calibrated thresholds

**Status:** proposed
**Date:** 2026-10-21

## Context

Semantic search must run on the user's machine (R4, privacy invariant), handle
French as well as English, fit the memory budget (P4) and support switching
models with a re-calibrated abstention threshold (R4, R5). Measured on
2026-10-21, on 4 cores, with models already downloaded, using the Python
fastembed package on the same ONNX models and runtime as the Rust crate (to be
re-measured with the Rust build, ADR-002):

| Model | Dim | Download | Load | Query | Resident memory | French probe (5 + 2 negatives) |
|---|---:|---:|---:|---:|---:|---|
| `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | 384 | 0.22 GB | 0.7 s | 4 ms | 0.67 GB | 4/5, negatives max cosine 0.15 |
| `minishlab/potion-multilingual-128M` (static) | 256 | 0.51 GB | 2.0 s | 0.1 ms | 1.18 GB | 4/5, negatives max cosine 0.12 |

## Decision

- **Runtime:** the `fastembed` crate on `ort` (ONNX Runtime, CPU), which
  ships both candidate models (and a quantised MiniLM) as of 2026-10-21.
- **Default model:** `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
  (Apache-2.0) for every language.
- **Model registry:** tiroir ships a small registry listing the supported
  models with their dimension, licence, query and passage prefixes, and a
  default abstention threshold calibrated on the bundled evaluation sets
  (V2). A user calibration (`tiroir eval --calibrate`, V4) is stored per store
  and model in the data directory and overrides the default.
- **Switching:** the model is chosen per machine in the configuration;
  changing it re-embeds every chunk (R4). The index records which model
  produced each vector and never mixes models in one search.
- **Download:** on first use, from Hugging Face, the documented source. A
  local model directory can be configured for offline machines. Once the
  model is present, it is loaded from disk and no request leaves the machine.

## Alternatives considered

- **The quantised MiniLM** - smaller and faster, to be evaluated on the
  bundled sets in the first milestone; it becomes the default only if its
  recall and abstention match the full model.
- **potion-multilingual-128M** - near-instant queries, but its resident memory
  alone exceeds P4, and query speed is not the bottleneck (ADR-009 keeps
  embedding out of the hook).
- **multilingual-e5-large** - stronger retrieval, but 2.2 GB and slow on a
  laptop CPU.
- **English-only models (bge-small)** - Basic Memory measured 75 % false
  positives on negative queries at a fixed threshold, against 0 % for the
  multilingual MiniLM.
- **An embedding API** - excluded by the privacy invariant.

## Consequences

The first semantic search on a machine waits for a 220 MB download. A model
switch costs a full re-embedding (minutes on 10,000 entries, within P3). The
default threshold is only as good as the bundled sets; stores far from them
need a user calibration, which is why evaluation is a Must.
