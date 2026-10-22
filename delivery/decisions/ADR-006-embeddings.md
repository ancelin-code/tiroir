# ADR-006: Embed on the server with ONNX Runtime, choose the default model by evaluation, and allow an OpenAI-compatible external service per store

**Status:** proposed
**Date:** 2026-10-22

## Context

Semantic search must handle French as well as English (R4), run on the server
by default, allow an external embedding service per store (R4), use as
default the best model the evaluation finds within the server budget (R4a,
P4: 4 GB for the whole server) and apply a calibrated abstention threshold per
model (R4, R5). A first probe on 2026-10-21 (Python fastembed, 4 cores, 5
French queries and 2 negatives) gave `paraphrase-multilingual-MiniLM-L12-v2`
4/5 with a negatives' maximum cosine of 0.15, in 0.67 GB resident; it is a
baseline, not a verdict.

## Decision

- **Runtime:** ONNX Runtime on CPU (`onnxruntime`), Hugging Face `tokenizers`
  for tokenisation, `huggingface_hub` for downloads; no PyTorch (ADR-002). A
  model is usable when it has an ONNX export and a tokenizer file.
- **Model registry**, shipped with tiroir: for each supported model, its
  source (repository and revision), dimension, licence, maximum input length,
  pooling and normalisation, query and passage prefixes, measured resident
  memory, and the default abstention threshold calibrated on the bundled
  evaluation sets (V2).
- **Candidates evaluated for the default** in the first milestone, all
  multilingual with ONNX exports and licences compatible with Apache-2.0: the
  MiniLM baseline above, `multilingual-e5-small`, `multilingual-e5-base`,
  `multilingual-e5-large` and `bge-m3`, plus any model added to the registry
  later. Each runs the full evaluation (V1–V3) on both bundled sets, measuring
  recall@5, MRR, false positives on negatives, query latency, full-index time
  for P3's store, and resident memory.
- **Choosing the default (R4a):** among candidates whose resident memory,
  added to the rest of the server measured under P6's store, keeps the server
  within P4 and whose index time meets P3, the highest recall@5 on the French
  set wins, MRR breaking ties. The comparison table is published in the
  documentation of each release and regenerated when a candidate is added.
  This record is amended with the result.
- **External service (R4):** one adapter, for the OpenAI-compatible
  `/v1/embeddings` API, which OpenAI, Mistral and self-hosted servers (Text
  Embeddings Inference, vLLM, Ollama) all expose. The administrator sets, per
  store, the base URL, the model name and an API key (stored in
  `<data>/secrets/`); the administration page states that the store's content
  is sent to that service, and asks for confirmation. A store using it gets
  its threshold from a calibration run (`tiroir admin eval --calibrate`) before
  semantic search is enabled; until then it searches lexically and says so.
- **Switching a store's model:** re-embeds every chunk of that store in the
  background, keeping the old vectors and threshold in service until the new
  ones are complete (R4). The index records which model produced each vector
  and never mixes models in one search. Stores of one server may use different
  models; a cross-store search fuses ranks, not cosines (ADR-007).
- **Download:** a local model is downloaded once, at first start or when
  selected, from its documented source into `<data>/models/`. An offline
  server can be given a model directory instead.
- **Calibration:** `tiroir admin eval --calibrate <store>` (V4) stores a
  threshold per store and model in `server.db`, overriding the registry's
  default.

## Alternatives considered

- **Fixing MiniLM as the default now** (the local-first design) - it fitted a
  1 GB laptop budget; on a server the budget allows larger models, and R4a asks
  for the best one, measured.
- **PyTorch with `sentence-transformers`** - every model without export work,
  but an image of several gigabytes and more memory at rest (ADR-002).
- **A model server container (Text Embeddings Inference)** - fast and broad,
  but a second container to run; it remains usable as an "external" service
  through the OpenAI-compatible adapter.
- **One adapter per vendor API** (Voyage, Cohere, Google…) - more choice, but
  each is code to maintain; the OpenAI-compatible API covers the main vendors
  and every self-hosted server. Others can be added behind the same interface.
- **English-only models** - Basic Memory measured 75 % false positives on
  negative queries at a fixed threshold, against 0 % for a multilingual model.

## Consequences

The first start downloads the default model (from about 0.2 GB to over 2 GB
depending on the winner), which the installation guide announces. Larger
models make full re-indexing slower; P3 bounds it. An external service sends
the store's content out of the server, which the invariant on network traffic
allows only for stores the administrator explicitly configured. The default
threshold is only as good as the bundled sets; stores far from them need a
calibration, which is why evaluation is a Must.
