"""A deterministic test `Embedder` that needs no model.

Each word is hashed into one of `DIMENSION` buckets, so texts sharing words
are close and texts sharing none are orthogonal.
"""

import hashlib
import re

import numpy as np
from numpy.typing import NDArray

from tiroir.core.embeddings.local import l2_normalize

DIMENSION = 64


class HashingEmbedder:
    """Embeds by hashing words into a fixed-dimension, L2-normalised vector."""

    def __init__(self, model_id: str = "test-hashing", dimension: int = DIMENSION):
        self._model_id = model_id
        self._dimension = dimension

    @property
    def model_id(self) -> str:
        """The identifier recorded with the vectors."""
        return self._model_id

    @property
    def dimension(self) -> int:
        """The vector length."""
        return self._dimension

    def embed_queries(self, texts: list[str]) -> NDArray[np.float32]:
        """Embed queries like passages: this embedder has no prefixes."""
        return self._embed(texts)

    def embed_passages(self, texts: list[str]) -> NDArray[np.float32]:
        """Embed passages."""
        return self._embed(texts)

    def _embed(self, texts: list[str]) -> NDArray[np.float32]:
        """One row per text: hashed word counts, scaled to unit length."""
        out = np.zeros((len(texts), self._dimension), dtype=np.float32)
        for row, text in enumerate(texts):
            for word in re.findall(r"\w+", text.lower()):
                digest = hashlib.sha256(word.encode()).digest()
                out[row, int.from_bytes(digest[:4], "big") % self._dimension] += 1.0
        return l2_normalize(out)
