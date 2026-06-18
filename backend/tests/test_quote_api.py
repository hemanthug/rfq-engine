from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.schemas.quote import MoldingQuoteWorkflowResult, QuoteWorkflowResult, SheetMetalQuoteWorkflowResult
from test_feature_extraction import _make_box_shape, _write_step, _write_through_hole_plate_step


def _post_quote(client: TestClient, step_path: Path, data: dict | None = None):
    with step_path.open("rb") as file_handle:
        return client.post(
            "/quotes/cnc",
            data=data or {},
            files={"file": (step_path.name, file_handle, "application/octet-stream")},
        )


def _post_molding_quote(client: TestClient, step_path: Path, data: dict | None = None):
    with step_path.open("rb") as file_handle:
        return client.post(
            "/quotes/injection-molding",
            data=data or {},
            files={"file": (step_path.name, file_handle, "application/octet-stream")},
        )


def _post_sheet_metal_quote(client: TestClient, step_path: Path, data: dict | None = None):
    with step_path.open("rb") as file_handle:
        return client.post(
            "/quotes/sheet-metal",
            data=data or {},
            files={"file": (step_path.name, file_handle, "application/octet-stream")},
        )


def test_cnc_quote_upload_returns_quote_and_preview(tmp_path: Path) -> None:
    step_path = tmp_path / "box.step"
    _write_step(step_path, _make_box_shape(40.0, 30.0, 20.0))
    client = TestClient(create_app(Settings(environment="test")))

    response = _post_quote(
        client,
        step_path,
        {
            "material": "aluminum_6061",
            "quantity": "2",
            "tolerance_class": "standard",
            "finish": "as_machined",
            "lead_time_class": "standard",
        },
    )

    assert response.status_code == 200
    result = QuoteWorkflowResult.model_validate(response.json())
    assert result.quote.process == "cnc_3_axis_milling"
    assert result.quote.subtotal >= 125.0
    assert result.preview.triangle_count > 0
    assert result.preview.vertex_count > 0
    assert result.preview.bbox.size == result.quote.source.source.bounding_box.size
    assert result.upload.filename == "box.step"
    assert result.upload.size_bytes > 0
    assert result.workflow.elapsed_ms >= 0


def test_injection_molding_quote_upload_returns_tooling_production_and_preview(tmp_path: Path) -> None:
    step_path = tmp_path / "box.step"
    _write_step(step_path, _make_box_shape(40.0, 30.0, 20.0))
    client = TestClient(create_app(Settings(environment="test")))

    response = _post_molding_quote(
        client,
        step_path,
        {
            "material": "abs",
            "quantity": "1000",
            "annual_volume": "10000",
            "cavities": "1",
            "mold_class": "production",
            "finish": "standard_spi_b3",
            "lead_time_class": "standard",
        },
    )

    assert response.status_code == 200
    result = MoldingQuoteWorkflowResult.model_validate(response.json())
    assert result.quote.process == "injection_molding"
    assert result.quote.tooling_cost > 0
    assert result.quote.production_subtotal > 0
    assert result.quote.total_first_order_cost == result.quote.tooling_cost + result.quote.production_subtotal
    assert result.preview.triangle_count > 0
    assert result.preview.bbox.size == result.quote.source.source.bounding_box.size
    assert "dfm_not_performed" in result.quote.assumptions


def test_sheet_metal_quote_upload_returns_quote_and_preview(tmp_path: Path) -> None:
    step_path = tmp_path / "thin_panel.step"
    _write_step(step_path, _make_box_shape(160.0, 90.0, 2.0))
    client = TestClient(create_app(Settings(environment="test")))

    response = _post_sheet_metal_quote(
        client,
        step_path,
        {
            "material": "aluminum_5052",
            "quantity": "2",
            "finish": "raw",
            "lead_time_class": "standard",
        },
    )

    assert response.status_code == 200
    result = SheetMetalQuoteWorkflowResult.model_validate(response.json())
    assert result.quote.process == "sheet_metal"
    assert result.quote.subtotal >= 125.0
    assert result.preview.triangle_count > 0
    assert result.quote.diagnostics.geometry_signals["raw_estimated_thickness_mm"] == pytest.approx(1.93, abs=0.05)
    assert result.quote.diagnostics.geometry_signals["estimated_thickness_mm"] == pytest.approx(2.053, abs=1e-3)


def test_cnc_quote_upload_uses_detected_hole_feature_operations(tmp_path: Path) -> None:
    step_path = tmp_path / "through_hole.step"
    _write_through_hole_plate_step(step_path)
    client = TestClient(create_app(Settings(environment="test")))

    response = _post_quote(client, step_path)

    assert response.status_code == 200
    result = QuoteWorkflowResult.model_validate(response.json())
    feature_ops = next(item for item in result.quote.line_items if item.code == "feature_operations")
    assert feature_ops.details["through_holes"] == 1
    assert result.preview.triangle_count > 0


def test_cnc_quote_for_htd_pulley_prices_only_conservative_holes() -> None:
    step_path = Path(__file__).parent / "fixtures" / "HTD5M-20W-48Z-D20.STEP"
    client = TestClient(create_app(Settings(environment="test")))

    response = _post_quote(client, step_path)

    assert response.status_code == 200
    result = QuoteWorkflowResult.model_validate(response.json())
    feature_ops = next(item for item in result.quote.line_items if item.code == "feature_operations")
    assert len(result.quote.source.holes) == 3
    assert feature_ops.details["through_holes"] == 3
    assert feature_ops.details["pockets"] == 0
    assert feature_ops.amount > 0
    assert len(result.quote.source.diagnostics.rejected_candidates) >= 140


def test_cnc_quote_upload_rejects_invalid_material(tmp_path: Path) -> None:
    step_path = tmp_path / "box.step"
    _write_step(step_path, _make_box_shape(40.0, 30.0, 20.0))
    client = TestClient(create_app(Settings(environment="test")))

    response = _post_quote(client, step_path, {"material": "titanium"})

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "pricing_input_invalid"


def test_injection_molding_quote_upload_rejects_invalid_material(tmp_path: Path) -> None:
    step_path = tmp_path / "box.step"
    _write_step(step_path, _make_box_shape(40.0, 30.0, 20.0))
    client = TestClient(create_app(Settings(environment="test")))

    response = _post_molding_quote(client, step_path, {"material": "pla"})

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "pricing_input_invalid"


def test_injection_molding_quote_upload_rejects_invalid_cavities(tmp_path: Path) -> None:
    step_path = tmp_path / "box.step"
    _write_step(step_path, _make_box_shape(40.0, 30.0, 20.0))
    client = TestClient(create_app(Settings(environment="test")))

    response = _post_molding_quote(client, step_path, {"cavities": "3"})

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "pricing_input_invalid"


def test_cnc_quote_upload_rejects_unsupported_extension(tmp_path: Path) -> None:
    step_path = tmp_path / "box.txt"
    step_path.write_text("not step", encoding="utf-8")
    client = TestClient(create_app(Settings(environment="test")))

    response = _post_quote(client, step_path)

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "cad_invalid_extension"


def test_cnc_quote_upload_rejects_invalid_step_content(tmp_path: Path) -> None:
    step_path = tmp_path / "invalid.step"
    step_path.write_text("ISO-10303-21;", encoding="utf-8")
    client = TestClient(create_app(Settings(environment="test")))

    response = _post_quote(client, step_path)

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "step_read_failed"


def test_cnc_quote_upload_rejects_oversized_file(tmp_path: Path) -> None:
    step_path = tmp_path / "too-large.step"
    step_path.write_bytes(b"ISO-10303-21;" * 10)
    client = TestClient(create_app(Settings(environment="test", upload_max_file_size_bytes=8)))

    response = _post_quote(client, step_path)

    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "upload_file_too_large"


def test_cnc_quote_upload_rejects_preview_mesh_too_large(tmp_path: Path) -> None:
    step_path = tmp_path / "box.step"
    _write_step(step_path, _make_box_shape(40.0, 30.0, 20.0))
    client = TestClient(create_app(Settings(environment="test", preview_max_triangles=1)))

    response = _post_quote(client, step_path)

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "preview_mesh_too_large"


def test_cnc_quote_upload_cleans_temp_directory_after_success_and_failure(tmp_path: Path) -> None:
    upload_temp_dir = tmp_path / "uploads"
    upload_temp_dir.mkdir()
    step_path = tmp_path / "box.step"
    _write_step(step_path, _make_box_shape(40.0, 30.0, 20.0))
    client = TestClient(create_app(Settings(environment="test", upload_temp_dir=str(upload_temp_dir))))

    success = _post_quote(client, step_path)
    failure = _post_quote(client, step_path, {"material": "titanium"})

    assert success.status_code == 200
    assert failure.status_code == 400
    assert list(upload_temp_dir.iterdir()) == []


def test_openapi_schema_includes_cnc_quote_route() -> None:
    client = TestClient(create_app(Settings(environment="test")))

    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/quotes/cnc" in response.json()["paths"]
    assert "/quotes/injection-molding" in response.json()["paths"]
    assert "/quotes/sheet-metal" in response.json()["paths"]
