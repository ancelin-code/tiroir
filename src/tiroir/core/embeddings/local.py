"""The local embedder: ONNX Runtime on CPU with a `tokenizers` tokenizer.

`onnxruntime` is imported when an embedder is built, not when this module is
imported, so that merely importing the package stays fast.
"""

from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray
from tokenizers import Tokenizer

from tiroir.core.embeddings.registry import ModelSpec

BATCH_SIZE = 32


def with_prefix(prefix: str, texts: list[str]) -> list[str]:
    """Return `texts` each preceded by `prefix`."""
    return [prefix + text for text in texts]


def pool(
    hidden: NDArray[np.float32], mask: NDArray[np.int64], pooling: str
) -> NDArray[np.float32]:
    """Reduce token states (batch, tokens, dim) to one row per text.

    `mean` averages the states of the real tokens (`mask` is 1), `cls` takes
    the first token's state.
    """
    if pooling == "cls":
        return hidden[:, 0, :].astype(np.float32)
    weights = mask[:, :, None].astype(np.float32)
    total = (hidden * weights).sum(axis=1)
    count = np.maximum(weights.sum(axis=1), 1e-9)
    return (total / count).astype(np.float32)


def l2_normalize(vectors: NDArray[np.float32]) -> NDArray[np.float32]:
    """Scale each row to unit length; a zero row stays zero."""
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return (vectors / np.maximum(norms, 1e-12)).astype(np.float32)


class LocalEmbedder:
    """Embeds with a model downloaded to a local directory (see `download`)."""

    def __init__(self, spec: ModelSpec, model_dir: Path) -> None:
        import onnxruntime

        self._spec = spec
        options = onnxruntime.SessionOptions()
        options.log_severity_level = 3
        self._session: Any = onnxruntime.InferenceSession(
            str(model_dir / spec.onnx_file),
            sess_options=options,
            providers=["CPUExecutionProvider"],
        )
        self._input_names = {i.name for i in self._session.get_inputs()}
        self._tokenizer = Tokenizer.from_file(str(model_dir / spec.tokenizer_file))
        self._tokenizer.enable_truncation(max_length=spec.max_tokens)
        self._tokenizer.enable_padding()

    @property
    def model_id(self) -> str:
        """The registry identifier of the model."""
        return self._spec.model_id

    @property
    def dimension(self) -> int:
        """The registry's vector length."""
        return self._spec.dimension

    def embed_queries(self, texts: list[str]) -> NDArray[np.float32]:
        """Embed queries, with the model's query prefix."""
        return self._embed(with_prefix(self._spec.query_prefix, texts))

    def embed_passages(self, texts: list[str]) -> NDArray[np.float32]:
        """Embed passages, with the model's passage prefix."""
        return self._embed(with_prefix(self._spec.passage_prefix, texts))

    def _embed(self, texts: list[str]) -> NDArray[np.float32]:
        """Run the model by batches and return one row per text, in order."""
        rows = [
            self._embed_batch(texts[start : start + BATCH_SIZE])
            for start in range(0, len(texts), BATCH_SIZE)
        ]
        if not rows:
            return np.zeros((0, self._spec.dimension), dtype=np.float32)
        return np.concatenate(rows)

    def _embed_batch(self, texts: list[str]) -> NDArray[np.float32]:
        """Tokenise, run and pool one batch."""
        encodings = self._tokenizer.encode_batch(texts)
        ids = np.array([e.ids for e in encodings], dtype=np.int64)
        mask = np.array([e.attention_mask for e in encodings], dtype=np.int64)
        feeds = {"input_ids": ids, "attention_mask": mask}
        if "token_type_ids" in self._input_names:
            feeds["token_type_ids"] = np.zeros_like(ids)
        hidden = self._session.run(None, feeds)[0]
        pooled = pool(hidden, mask, self._spec.pooling)
        return l2_normalize(pooled) if self._spec.normalize else pooled
