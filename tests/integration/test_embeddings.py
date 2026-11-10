import json
import os
import socket
import subprocess
import sys
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, override

import numpy as np
import pytest
from loguru import logger

from tiroir.core.embeddings import download
from tiroir.core.embeddings.download import ensure_model
from tiroir.core.embeddings.external import ExternalEmbedder
from tiroir.core.embeddings.local import LocalEmbedder
from tiroir.core.embeddings.registry import MODELS
from tiroir.core.errors import CoreError

MODELS_DIR = os.environ.get("TIROIR_TEST_MODELS")
needs_models = pytest.mark.skipif(
    not MODELS_DIR, reason="TIROIR_TEST_MODELS names no model directory"
)
STORE = "7c1d4a62-3e5b-4f08-9a17-d2b6c8e0f413"
SECRET_KEY = "sk-test-secret"


class _Service:
    """A local OpenAI-compatible server recording requests; it can fail."""

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self.status = 200
        self.delay = 0.0
        # When set, each response's vectors are one coordinate longer.
        self.growing = False
        self.indices: list[int] | None = None
        service = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                service.requests.append(
                    {
                        "path": self.path,
                        "auth": self.headers["Authorization"],
                        "body": body,
                    }
                )
                if service.delay:
                    threading.Event().wait(service.delay)
                if service.status != 200:
                    self.send_response(service.status)
                    self.end_headers()
                    return
                # Answer in reverse order to prove the client sorts by index.
                width = len(service.requests) if service.growing else 1
                indices = service.indices or range(len(body["input"]))
                data = [
                    {"index": i, "embedding": [float(len(text))] + [1.0] * width}
                    for i, text in zip(indices, body["input"], strict=True)
                ][::-1]
                payload = json.dumps({"data": data}).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            @override
            def log_message(self, format: str, *args: Any) -> None:
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server.server_address[1]}"


@pytest.fixture
def service() -> Iterator[_Service]:
    svc = _Service()
    yield svc
    svc.server.shutdown()
    svc.server.server_close()


def _client(service: _Service, tmp_path: Path, **kwargs: Any) -> ExternalEmbedder:
    key = tmp_path / "key"
    key.write_text(SECRET_KEY + "\n")
    return ExternalEmbedder(
        store_id=STORE,
        base_url=service.url + "/",
        model="text-embedding-test",
        api_key_file=key,
        **kwargs,
    )


def test_external_sends_batches_with_key_and_keeps_order(
    service: _Service, tmp_path: Path
) -> None:
    # Given
    client = _client(service, tmp_path, batch_size=2)
    texts = ["a", "bb", "ccc", "dddd", "eeeee"]

    # When
    vectors = client.embed_passages(texts)

    # Then
    assert [r["path"] for r in service.requests] == ["/v1/embeddings"] * 3
    assert [r["body"]["input"] for r in service.requests] == [
        ["a", "bb"],
        ["ccc", "dddd"],
        ["eeeee"],
    ]
    assert {r["auth"] for r in service.requests} == {f"Bearer {SECRET_KEY}"}
    assert {r["body"]["model"] for r in service.requests} == {"text-embedding-test"}
    assert vectors.dtype == np.float32
    assert vectors.shape == (5, 2)
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0)
    # The first coordinate grows with the text length: order is preserved.
    assert list(vectors[:, 0]) == sorted(vectors[:, 0])
    assert client.dimension == 2
    assert client.model_id == "text-embedding-test"


def test_external_dimension_change_between_batches_is_unavailable(
    service: _Service, tmp_path: Path
) -> None:
    # Given
    service.growing = True
    client = _client(service, tmp_path, batch_size=1)

    # When
    with pytest.raises(CoreError) as raised:
        client.embed_passages(["a", "b"])

    # Then
    assert raised.value.code == "embedding.external-unavailable"


def test_external_duplicate_indices_are_unavailable(
    service: _Service, tmp_path: Path
) -> None:
    # Given
    service.indices = [0, 0]
    client = _client(service, tmp_path)

    # When
    with pytest.raises(CoreError) as raised:
        client.embed_passages(["a", "b"])

    # Then
    assert raised.value.code == "embedding.external-unavailable"


def test_external_learns_the_dimension_without_an_extra_request(
    service: _Service, tmp_path: Path
) -> None:
    # Given
    client = _client(service, tmp_path)
    client.embed_passages(["a"])

    # When
    dimension = client.dimension

    # Then
    assert dimension == 2
    assert len(service.requests) == 1


def test_external_http_error_is_unavailable_and_logs_no_secret(
    service: _Service, tmp_path: Path
) -> None:
    # Given
    service.status = 500
    client = _client(service, tmp_path)
    lines: list[str] = []
    sink = logger.add(lines.append, format="{message}")

    # When
    try:
        with pytest.raises(CoreError) as raised:
            client.embed_queries(["secret memory text"])
    finally:
        logger.remove(sink)

    # Then
    assert raised.value.code == "embedding.external-unavailable"
    logged = "".join(lines)
    assert STORE in logged
    assert "HTTPStatusError" in logged
    assert "secret memory text" not in logged
    assert SECRET_KEY not in logged


def test_external_timeout_is_unavailable(service: _Service, tmp_path: Path) -> None:
    # Given
    service.delay = 1.0
    client = _client(service, tmp_path, timeout=0.2)

    # When / Then
    with pytest.raises(CoreError) as raised:
        client.embed_passages(["x"])
    assert raised.value.code == "embedding.external-unavailable"


def test_external_missing_key_file_is_unavailable(
    service: _Service, tmp_path: Path
) -> None:
    # Given
    client = ExternalEmbedder(
        store_id=STORE,
        base_url=service.url,
        model="m",
        api_key_file=tmp_path / "absent",
    )

    # When / Then
    with pytest.raises(CoreError) as raised:
        client.embed_passages(["x"])
    assert raised.value.code == "embedding.external-unavailable"
    assert service.requests == []


def test_offline_directory_takes_precedence(tmp_path: Path) -> None:
    # Given
    spec = MODELS["multilingual-e5-small"]
    offline = tmp_path / "offline" / spec.model_id
    for name in spec.files:
        (offline / name).parent.mkdir(parents=True, exist_ok=True)
        (offline / name).write_bytes(b"x")
    env = {download.MODELS_ENV: str(tmp_path / "offline")}

    # When
    directory = ensure_model(spec, tmp_path / "data", env)

    # Then
    assert directory == offline
    assert not (tmp_path / "data").exists()


def test_offline_directory_without_the_model_fails(tmp_path: Path) -> None:
    # Given
    spec = MODELS["multilingual-e5-small"]
    env = {download.MODELS_ENV: str(tmp_path)}

    # When / Then
    with pytest.raises(CoreError) as raised:
        ensure_model(spec, tmp_path / "data", env)
    assert raised.value.code == "embedding.model-missing"


def test_complete_directory_makes_no_download(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given
    spec = MODELS["multilingual-e5-small"]
    directory = tmp_path / "models" / spec.model_id
    for name in spec.files:
        (directory / name).parent.mkdir(parents=True, exist_ok=True)
        (directory / name).write_bytes(b"x")

    def refuse(**_: Any) -> None:
        raise AssertionError("network used")

    monkeypatch.setattr(download, "hf_hub_download", refuse)

    # When
    found = ensure_model(spec, tmp_path, {})

    # Then
    assert found == directory


@needs_models
def test_minilm_embeds_french_and_reloads_offline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given
    assert MODELS_DIR
    spec = MODELS["paraphrase-multilingual-MiniLM-L12-v2"]
    data_dir = Path(MODELS_DIR)
    directory = ensure_model(spec, data_dir, {})
    assert directory == data_dir / "models" / spec.model_id

    def refuse(*_: Any, **__: Any) -> None:
        raise AssertionError("network used")

    monkeypatch.setattr(download, "hf_hub_download", refuse)
    monkeypatch.setattr(socket.socket, "connect", refuse)

    # When
    reloaded = ensure_model(spec, data_dir, {})
    embedder = LocalEmbedder(spec, reloaded)
    query = embedder.embed_queries(["échéance de TVA"])
    passages = embedder.embed_passages(
        ["date limite de la déclaration de TVA", "rendez-vous chez le dentiste"]
    )

    # Then
    assert reloaded == directory
    assert query.dtype == np.float32
    assert query.shape == (1, spec.dimension)
    assert passages.shape == (2, spec.dimension)
    assert np.allclose(np.linalg.norm(passages, axis=1), 1.0, atol=1e-5)
    assert embedder.dimension == spec.dimension
    close, far = (passages @ query[0]).tolist()
    assert close > far


def test_importing_the_package_does_not_load_onnxruntime() -> None:
    # Given
    code = (
        "import sys, tiroir.core.embeddings.local, tiroir.core.embeddings.download,"
        " tiroir.core.embeddings.external;"
        "sys.exit('onnxruntime' in sys.modules)"
    )

    # When
    result = subprocess.run([sys.executable, "-c", code], check=False)

    # Then
    assert result.returncode == 0
