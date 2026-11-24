"""Text embedding behind one interface (ADR-006).

A local ONNX Runtime embedder and an OpenAI-compatible external client both
implement `Embedder`. This package imports neither `onnxruntime` nor a model
file: `tiroir.core.embeddings.local` does, when a local embedder is built.
"""

from typing import Protocol

import numpy as np
from numpy.typing import NDArray


class Embedder(Protocol):
    """Turns texts into unit-length vectors, with one model for both kinds."""

    @property
    def model_id(self) -> str:
        """The identifier of the model that produces the vectors."""
        ...

    @property
    def dimension(self) -> int:
        """The length of every vector."""
        ...

    def embed_queries(self, texts: list[str]) -> NDArray[np.float32]:
        """Embed search queries: a float32 array, one L2-normalised row per text."""
        ...

    def embed_passages(self, texts: list[str]) -> NDArray[np.float32]:
        """Embed stored passages: a float32 array, one L2-normalised row per text."""
        ...
