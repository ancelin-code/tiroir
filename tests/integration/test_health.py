from importlib.metadata import version
from pathlib import Path

from loguru import logger
from starlette.testclient import TestClient

from tiroir.server.app import create_app


def test_health_answers_ready_with_version(tmp_path: Path) -> None:
    # Given
    app = create_app(tmp_path)

    # When
    with TestClient(app) as client:
        response = client.get("/health")

    # Then
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "version": version("tiroir")}
    assert (tmp_path / "server.db").exists()


def test_health_answers_503_before_startup_ends(tmp_path: Path) -> None:
    # Given
    app = create_app(tmp_path)
    client = TestClient(app)  # no lifespan: the server has not started

    # When
    response = client.get("/health")

    # Then
    assert response.status_code == 503
    assert response.json()["status"] == "starting"


def test_request_log_has_template_status_and_no_query_or_body(tmp_path: Path) -> None:
    # Given
    records: list[dict[str, object]] = []
    sink = logger.add(lambda m: records.append(m.record["extra"]), level="INFO")
    app = create_app(tmp_path)

    # When
    with TestClient(app) as client:
        client.get("/health?secret=hunter2")
        client.post("/nowhere/private-name", content=b"memory text")
    logger.remove(sink)

    # Then
    requests = [r for r in records if "status" in r]
    assert requests[0] == {
        "method": "GET",
        "path": "/health",
        "status": 200,
        "duration_ms": requests[0]["duration_ms"],
        "member": "",
    }
    assert requests[1]["path"] == "<unmatched>"
    assert requests[1]["status"] == 404
    dump = repr(records)
    assert "hunter2" not in dump
    assert "memory text" not in dump
    assert "private-name" not in dump
