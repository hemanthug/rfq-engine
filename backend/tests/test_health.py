from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_liveness_endpoint_returns_typed_response() -> None:
    client = TestClient(create_app(Settings(environment="test")))

    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_endpoint_returns_runtime_metadata() -> None:
    client = TestClient(create_app(Settings(environment="test")))

    response = client.get("/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["ready"] is True
    assert body["service"] == "RFQ Engine Backend"
    assert body["version"] == "0.1.0"
    assert body["environment"] == "test"
    assert body["python_version"].startswith("3.10.")

