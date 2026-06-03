from pathlib import Path

import pytest

from app.cad.errors import PreviewMeshTooLargeError
from app.cad.preview_mesh import PreviewMeshBuilder
from app.cad.step_reader import StepReader
from app.config import Settings
from test_feature_extraction import _make_box_shape, _write_step


def test_generated_box_preview_mesh_contains_renderable_buffers(tmp_path: Path) -> None:
    step_path = tmp_path / "box.step"
    _write_step(step_path, _make_box_shape(10.0, 20.0, 30.0))
    context = StepReader().load_context(step_path)

    result = PreviewMeshBuilder().build(context.shape, context.parse_result.bounding_box)

    assert result.schema_version == "1.0"
    assert result.units == "MM"
    assert result.triangle_count > 0
    assert result.vertex_count > 0
    assert len(result.positions) == result.vertex_count * 3
    assert len(result.normals) == result.vertex_count * 3
    assert len(result.indices) == result.triangle_count * 3
    assert result.bbox.size == pytest.approx([10.0, 20.0, 30.0], abs=1e-5)
    assert result.model_dump_json()


def test_preview_mesh_raises_when_triangle_limit_is_tiny(tmp_path: Path) -> None:
    step_path = tmp_path / "box.step"
    _write_step(step_path, _make_box_shape(10.0, 20.0, 30.0))
    settings = Settings(preview_max_triangles=1)
    context = StepReader(settings).load_context(step_path)

    with pytest.raises(PreviewMeshTooLargeError) as exc_info:
        PreviewMeshBuilder(settings).build(context.shape, context.parse_result.bounding_box)

    assert exc_info.value.as_dict()["code"] == "preview_mesh_too_large"
