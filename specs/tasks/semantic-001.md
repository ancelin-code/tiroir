---
id: semantic-001
title: Embed text on the server with ONNX Runtime, from a registry of candidate models
type: feat
epic: semantic
depends_on: []
parallel: true
conflicts_with: [bench-001]
tier: build
review: [security]
---

## Context

Semantic search needs an embedding model that handles the store's language,
run on the server by default, or an OpenAI-compatible external service chosen
per store ([ADR-006](../decisions/ADR-006-embeddings.md)). Nothing in the core
embeds yet. This task builds the embedding layer only: a registry of the
candidate models, a local ONNX embedder, the one-time download, and the
external client, all behind one interface. Indexing vectors, searching them
and choosing a model per store come in `semantic-002` to `semantic-004`.

This is the only task of the milestone that adds runtime dependencies
(ADR-002's list: `onnxruntime`, `tokenizers`, `huggingface_hub`, `numpy`), so
no other task edits `pyproject.toml` or `uv.lock`.

## Covers

- R4 (part): the local embedder, the registry of multilingual candidates and
  the OpenAI-compatible client; choosing a model per store, the re-index on
  change and the per-model threshold come in `semantic-004`

## Scope

Files this task is expected to touch:

- `pyproject.toml`, `uv.lock`: add `onnxruntime`, `tokenizers`,
  `huggingface_hub`, `numpy`
- `src/tiroir/core/embeddings/__init__.py`: the `Embedder` protocol:
  `model_id`, `dimension`, `embed_queries(texts) -> numpy.ndarray`,
  `embed_passages(texts) -> numpy.ndarray`, float32, one L2-normalised row per
  text
- `src/tiroir/core/embeddings/registry.py`: one frozen `ModelSpec` per
  supported model, with ADR-006's attributes (source repository and pinned
  revision, ONNX file, dimension, licence, maximum input tokens, pooling,
  normalisation, query and passage prefixes, measured resident memory, default
  threshold or `None` until calibrated). The five candidates of ADR-006:
  `paraphrase-multilingual-MiniLM-L12-v2`, `multilingual-e5-small`,
  `multilingual-e5-base`, `multilingual-e5-large`, `bge-m3`; a
  `DEFAULT_MODEL` constant, provisionally MiniLM (the evaluation in
  `eval-003` replaces it)
- `src/tiroir/core/embeddings/local.py`: the ONNX Runtime embedder
  (CPU provider, `tokenizers` tokenizer, truncation at the model's maximum,
  batching, mean or CLS pooling per spec, prefixes per spec)
- `src/tiroir/core/embeddings/download.py`: fetch a model's files at its
  pinned revision into `<data>/models/<model-id>/` once; use that directory
  without any network access when it is complete; a directory given by
  `TIROIR_MODELS` (an offline server) takes precedence
- `src/tiroir/core/embeddings/external.py`: the OpenAI-compatible
  `/v1/embeddings` client on `httpx` (base URL, model name, API key read from
  a file path), batched, with a timeout; failures raise
  `CoreError("embedding.external-unavailable")`
- `tests/unit/core/embeddings/test_registry.py`,
  `tests/unit/core/embeddings/test_local.py` (pooling, prefixes and
  normalisation on given arrays, no model file),
  `tests/integration/test_embeddings.py` (the external client against a local
  HTTP server in the test; the local embedder on a real model, skipped unless
  `TIROIR_TEST_MODELS` names a directory holding it)
- `tests/integration/embedding_support.py`: a deterministic test `Embedder`
  (hashing words into a fixed-dimension vector) that later tasks use, so the
  default test run needs no model
- `mise.toml`: a `test:model` task running the model tests with
  `TIROIR_TEST_MODELS` set to a cache directory
- `docs/install/vps.md`: the one-time model download at first start, its size
  and the `TIROIR_MODELS` offline option

Out of scope:

- vectors in the index, the background embedding, model loading at start
  (`semantic-002`)
- vector search and fusion (`semantic-003`)
- the per-store model choice, secrets in `<data>/secrets/`, the
  `tiroir admin embedding` command (`semantic-004`)
- choosing the default model (`eval-003`)

## Acceptance criteria

- `uv run python -c "import onnxruntime, tokenizers, huggingface_hub, numpy"`
  works from the lock file, and `mise run licenses` passes with the new
  dependencies.
- The registry lists the five candidates, each with a pinned revision, a
  licence compatible with Apache-2.0 and every ADR-006 attribute; a unit test
  fails if one is missing.
- With `TIROIR_TEST_MODELS` set, `mise run test:model` embeds a French query
  and passage with the MiniLM model: vectors have the registry's dimension and
  unit norm, and `échéance de TVA` is closer to `date limite de la
  déclaration de TVA` than to `rendez-vous chez le dentiste`.
- A second load of a downloaded model makes no network request (checked by a
  test that blocks the network after the first download, under `test:model`).
- The external client sends the texts in batches to `POST
  <base>/v1/embeddings` with the bearer key and the model name, returns the
  vectors in input order, and raises `embedding.external-unavailable` on a
  timeout or an HTTP error; its log lines carry the store id and the error
  class, never a text or the key (Y5).
- `import tiroir.core.embeddings` does not import `onnxruntime` until a local
  embedder is built, so `tiroir admin` commands start as fast as before.
- `mise run check` passes, and `mise run image` still reports a compressed
  image under 600 MB (ADR-002).

## Validation

`mise run test -- tests/unit/core/embeddings tests/integration/test_embeddings.py`,
`mise run test:model` on a machine with network access, then `mise run check`
and `mise run image`.
