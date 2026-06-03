from pathlib import Path

import pytest

from app.cad.feature_extractor import FeatureExtractor
from app.schemas.features import FeatureExtractionResult


def _write_step(path: Path, shape: object) -> None:
    from OCC.Core.IFSelect import IFSelect_RetDone
    from OCC.Core.STEPControl import STEPControl_AsIs, STEPControl_Writer

    writer = STEPControl_Writer()
    transfer_status = writer.Transfer(shape, STEPControl_AsIs)
    assert transfer_status == IFSelect_RetDone
    write_status = writer.Write(str(path))
    assert write_status == IFSelect_RetDone


def _make_box_shape(x: float, y: float, z: float) -> object:
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox

    return BRepPrimAPI_MakeBox(x, y, z).Shape()


def _make_box_at_shape(x: float, y: float, z: float, dx: float, dy: float, dz: float) -> object:
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCC.Core.gp import gp_Trsf, gp_Vec

    shape = BRepPrimAPI_MakeBox(dx, dy, dz).Shape()
    transform = gp_Trsf()
    transform.SetTranslation(gp_Vec(x, y, z))
    return BRepBuilderAPI_Transform(shape, transform, True).Shape()


def _make_vertical_cylinder_shape(x: float, y: float, z: float, radius: float, height: float) -> object:
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCC.Core.gp import gp_Trsf, gp_Vec

    shape = BRepPrimAPI_MakeCylinder(radius, height).Shape()
    transform = gp_Trsf()
    transform.SetTranslation(gp_Vec(x, y, z))
    return BRepBuilderAPI_Transform(shape, transform, True).Shape()


def _cut(base: object, tool: object) -> object:
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut

    operation = BRepAlgoAPI_Cut(base, tool)
    operation.Build()
    assert operation.IsDone()
    return operation.Shape()


def _write_box_step(path: Path) -> None:
    _write_step(path, _make_box_shape(10.0, 20.0, 30.0))


def _write_through_hole_plate_step(path: Path) -> None:
    plate = _make_box_shape(40.0, 30.0, 10.0)
    cutter = _make_vertical_cylinder_shape(20.0, 15.0, -5.0, 5.0, 20.0)
    _write_step(path, _cut(plate, cutter))


def _write_blind_hole_block_step(path: Path) -> None:
    block = _make_box_shape(40.0, 30.0, 20.0)
    cutter = _make_vertical_cylinder_shape(20.0, 15.0, 8.0, 4.0, 20.0)
    _write_step(path, _cut(block, cutter))


def _write_rectangular_pocket_block_step(path: Path) -> None:
    block = _make_box_shape(40.0, 30.0, 20.0)
    cutter = _make_box_at_shape(10.0, 8.0, 10.0, 20.0, 14.0, 20.0)
    _write_step(path, _cut(block, cutter))


def test_generated_box_feature_inventory_has_only_planar_faces(tmp_path: Path) -> None:
    step_path = tmp_path / "box.step"
    _write_box_step(step_path)

    result = FeatureExtractor().extract_from_path(str(step_path))

    assert isinstance(result, FeatureExtractionResult)
    assert len(result.faces) == 6
    assert {face.surface_type for face in result.faces} == {"plane"}
    assert len(result.edges) == 12
    assert len(result.adjacency) == 12
    assert result.holes == []
    assert result.pockets == []
    assert result.source.bounding_box.size == pytest.approx([10.0, 20.0, 30.0], abs=1e-5)
    assert result.source.mass_properties.volume == pytest.approx(6000.0, abs=1e-5)
    assert "threads" in result.diagnostics.deferred_feature_types


def test_generated_through_hole_plate_detects_simple_hole(tmp_path: Path) -> None:
    step_path = tmp_path / "through_hole_plate.step"
    _write_through_hole_plate_step(step_path)

    result = FeatureExtractor().extract_from_path(str(step_path))

    through_holes = [hole for hole in result.holes if hole.hole_type == "through"]
    assert len(through_holes) == 1
    assert through_holes[0].diameter == pytest.approx(10.0, abs=1e-5)
    assert through_holes[0].depth == pytest.approx(10.0, abs=1e-5)
    assert through_holes[0].confidence > 0.7


def test_generated_blind_hole_block_detects_simple_blind_hole(tmp_path: Path) -> None:
    step_path = tmp_path / "blind_hole_block.step"
    _write_blind_hole_block_step(step_path)

    result = FeatureExtractor().extract_from_path(str(step_path))

    blind_holes = [hole for hole in result.holes if hole.hole_type == "blind"]
    assert len(blind_holes) == 1
    assert blind_holes[0].diameter == pytest.approx(8.0, abs=1e-5)
    assert blind_holes[0].depth == pytest.approx(12.0, abs=1e-5)
    assert blind_holes[0].confidence > 0.8


def test_generated_rectangular_pocket_block_detects_pocket_candidate(tmp_path: Path) -> None:
    step_path = tmp_path / "rectangular_pocket_block.step"
    _write_rectangular_pocket_block_step(step_path)

    result = FeatureExtractor().extract_from_path(str(step_path))

    assert len(result.pockets) >= 1
    pocket = max(result.pockets, key=lambda candidate: len(candidate.side_face_ids))
    assert pocket.pocket_type == "candidate_planar_bottom"
    assert len(pocket.side_face_ids) == 4
    assert pocket.confidence > 0.6
    assert "rim_supported_sidewalls" in pocket.evidence


def test_public_step_fixture_feature_extraction_smoke() -> None:
    fixture = Path(__file__).parent / "fixtures" / "step_tools_io1_ug_214.stp"
    result = FeatureExtractor().extract_from_path(str(fixture))

    assert len(result.faces) > 0
    assert len(result.edges) > 0
    assert len(result.adjacency) == len(result.edges)
    assert result.source.file.source_name == fixture.name
    assert result.model_dump_json()


def test_flx_4589_shaft_teeth_are_not_detected_as_holes() -> None:
    fixture = Path(__file__).parent / "fixtures" / "flx-4589.stp"
    result = FeatureExtractor().extract_from_path(str(fixture))

    assert result.source.file.source_name == fixture.name
    assert result.source.diagnostics.source_length_units == ["INCH"]
    assert result.source.bounding_box.size == pytest.approx(
        [22.278387646866, 22.278387646866, 87.07120419072943],
        abs=1e-5,
    )
    assert result.holes == []
    assert result.pockets == []
    assert {
        candidate.reason
        for candidate in result.diagnostics.rejected_candidates
        if candidate.candidate_type == "cylindrical_hole"
    } == {"external_profile_cylindrical_flank"}
    assert len(result.diagnostics.rejected_candidates) == 12
    assert result.model_dump_json()


def test_htd_pulley_tooth_arcs_are_not_detected_as_holes() -> None:
    fixture = Path(__file__).parent / "fixtures" / "HTD5M-20W-48Z-D20.STEP"
    result = FeatureExtractor().extract_from_path(str(fixture))

    assert result.source.file.source_name == fixture.name
    assert result.source.diagnostics.source_length_units == ["millimetre"]
    assert result.source.bounding_box.size == pytest.approx([38.0, 80.0, 80.0], abs=1e-5)
    assert len(result.holes) == 3
    assert result.pockets == []
    assert [round(hole.diameter, 1) for hole in result.holes] == [80.0, 60.0, 20.0]
    rejected_reasons = {
        candidate.reason
        for candidate in result.diagnostics.rejected_candidates
        if candidate.candidate_type == "cylindrical_hole"
    }
    assert "tooth_root_cylindrical_arc" in rejected_reasons
    assert len(result.diagnostics.rejected_candidates) >= 140
    assert result.model_dump_json()


def test_feature_ids_are_deterministic_within_single_extraction(tmp_path: Path) -> None:
    step_path = tmp_path / "box.step"
    _write_box_step(step_path)

    result = FeatureExtractor().extract_from_path(str(step_path))

    assert [face.face_id for face in result.faces] == [f"face_{index:04d}" for index in range(1, 7)]
    assert result.faces[0].edge_ids == sorted(result.faces[0].edge_ids)
    assert [edge.edge_id for edge in result.edges] == [
        f"edge_{index:04d}" for index in range(1, len(result.edges) + 1)
    ]
