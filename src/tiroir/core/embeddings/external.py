"""Client for an OpenAI-compatible `/v1/embeddings` service (ADR-006)."""

from pathlib import Path

import httpx
import numpy as np
from loguru import logger
from numpy.typing import NDArray

from tiroir.core.embeddings.local import l2_normalize
from tiroir.core.errors import CoreError

BATCH_SIZE = 64
TIMEOUT_SECONDS = 30.0
_UNAVAILABLE = "embedding.external-unavailable"


class ExternalEmbedder:
    """Embeds by calling an external service; the texts leave the server."""

    def __init__(
        self,
        *,
        store_id: str,
        base_url: str,
        model: str,
        api_key_file: Path,
        dimension: int | None = None,
        batch_size: int = BATCH_SIZE,
        timeout: float = TIMEOUT_SECONDS,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._store_id = store_id
        self._url = base_url.rstrip("/") + "/v1/embeddings"
        self._model = model
        self._key_file = api_key_file
        self._dimension = dimension
        self._batch_size = batch_size
        self._client = httpx.Client(timeout=timeout, transport=transport)

    @property
    def model_id(self) -> str:
        """The model name sent to the service."""
        return self._model

    @property
    def dimension(self) -> int:
        """The vector length; learnt from the service on first use if not given."""
        if self._dimension is None:
            self._dimension = int(self.embed_passages(["dimension"]).shape[1])
        return self._dimension

    def embed_queries(self, texts: list[str]) -> NDArray[np.float32]:
        """Embed queries; the service applies no prefix."""
        return self._embed(texts)

    def embed_passages(self, texts: list[str]) -> NDArray[np.float32]:
        """Embed passages; the service applies no prefix."""
        return self._embed(texts)

    def _embed(self, texts: list[str]) -> NDArray[np.float32]:
        """Send `texts` by batches and return the vectors in input order."""
        rows: list[NDArray[np.float32]] = []
        for start in range(0, len(texts), self._batch_size):
            rows.append(self._embed_batch(texts[start : start + self._batch_size]))
        if not rows:
            return np.zeros((0, self._dimension or 0), dtype=np.float32)
        return np.concatenate(rows)

    def _embed_batch(self, texts: list[str]) -> NDArray[np.float32]:
        """POST one batch; raise `embedding.external-unavailable` on any failure."""
        try:
            key = self._key_file.read_text(encoding="utf-8").strip()
            response = self._client.post(
                self._url,
                json={"model": self._model, "input": texts},
                headers={"Authorization": f"Bearer {key}"},
            )
            response.raise_for_status()
            items = sorted(response.json()["data"], key=lambda item: item["index"])
            if [item["index"] for item in items] != list(range(len(texts))):
                raise ValueError("unexpected embedding indices")
            vectors = np.array([item["embedding"] for item in items], dtype=np.float32)
            if vectors.ndim != 2:
                raise ValueError("unexpected embeddings shape")
            if self._dimension is None:
                self._dimension = int(vectors.shape[1])
            elif vectors.shape[1] != self._dimension:
                raise ValueError("unexpected embedding dimension")
        except (httpx.HTTPError, OSError, ValueError, KeyError, TypeError) as error:
            logger.error(
                "external embedding failed for store {}: {}",
                self._store_id,
                type(error).__name__,
            )
            raise CoreError(
                _UNAVAILABLE, "the embedding service is unavailable"
            ) from error
        return l2_normalize(vectors)
