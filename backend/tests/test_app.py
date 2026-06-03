from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_app_factory_creates_fastapi_application() -> None:
    app = create_app(
        Settings(
            app_name="Test RFQ Backend",
            app_version="9.9.9",
            environment="test",
        )
    )

    assert isinstance(app, FastAPI)
    assert app.title == "Test RFQ Backend"
    assert app.version == "9.9.9"


def test_root_returns_service_metadata() -> None:
    client = TestClient(create_app(Settings(environment="test")))

    response = client.get("/")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "RFQ Engine Backend"
    assert body["version"] == "0.1.0"
    assert body["environment"] == "test"
    assert body["python_version"].startswith("3.10.")


def test_openapi_schema_is_reachable() -> None:
    client = TestClient(create_app(Settings(environment="test")))

    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert response.json()["info"]["title"] == "RFQ Engine Backend"

