from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.schemas.preview import CadPreviewWorkflowResult
from test_feature_extraction import _make_box_shape, _write_step


def _post_preview(client: TestClient, step_path: Path):
    with step_path.open("rb") as file_handle:
        return client.post(
            "/cad/preview",
            files={"file": (step_path.name, file_handle, "application/octet-stream")},
        )


def test_cad_preview_upload_returns_mesh_and_source_facts(tmp_path: Path) -> None:
    step_path = tmp_path / "box.step"
    _write_step(step_path, _make_box_shape(10.0, 20.0, 30.0))
    client = TestClient(create_app(Settings(environment="test")))

    response = _post_preview(client, step_path)

    assert response.status_code == 200
    result = CadPreviewWorkflowResult.model_validate(response.json())
    assert result.preview.triangle_count > 0
    assert result.preview.vertex_count > 0
    assert result.preview.bbox.size == result.source.bounding_box.size
    assert result.process_fit is not None
    assert len(result.process_fit.ranked_processes) == 2
    assert result.process_fit.recommended_process in {"cnc", "sheet_metal"}
    assert result.source.bounding_box.size == pytest.approx([10.0, 20.0, 30.0], abs=1e-5)
    assert result.upload.filename == "box.step"
    assert result.upload.size_bytes > 0
    assert result.workflow.elapsed_ms >= 0


def test_cad_preview_upload_rejects_invalid_step_content(tmp_path: Path) -> None:
    step_path = tmp_path / "invalid.step"
    step_path.write_text("ISO-10303-21;", encoding="utf-8")
    client = TestClient(create_app(Settings(environment="test")))

    response = _post_preview(client, step_path)

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "step_read_failed"


def test_openapi_schema_includes_cad_preview_route() -> None:
    client = TestClient(create_app(Settings(environment="test")))

    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/cad/preview" in response.json()["paths"]
