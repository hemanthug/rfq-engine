from pathlib import Path

import pytest

from app.cad.errors import CadFileMissingError, CadInvalidExtensionError, StepReadError
from app.cad.step_reader import StepReader
from app.config import Settings
from app.schemas.cad import StepParseResult


def _write_box_step(path: Path, x: float = 10.0, y: float = 20.0, z: float = 30.0) -> None:
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCC.Core.IFSelect import IFSelect_RetDone
    from OCC.Core.STEPControl import STEPControl_AsIs, STEPControl_Writer

    shape = BRepPrimAPI_MakeBox(x, y, z).Shape()
    writer = STEPControl_Writer()
    transfer_status = writer.Transfer(shape, STEPControl_AsIs)
    assert transfer_status == IFSelect_RetDone
    write_status = writer.Write(str(path))
    assert write_status == IFSelect_RetDone


def test_missing_file_raises_structured_error(tmp_path: Path) -> None:
    missing = tmp_path / "missing.step"

    with pytest.raises(CadFileMissingError) as exc_info:
        StepReader().parse(missing)

    assert exc_info.value.as_dict()["code"] == "cad_file_missing"


def test_unsupported_extension_is_rejected_before_occ_import(tmp_path: Path) -> None:
    unsupported = tmp_path / "part.txt"
    unsupported.write_text("not a STEP file", encoding="utf-8")

    with pytest.raises(CadInvalidExtensionError) as exc_info:
        StepReader().parse(unsupported)

    error = exc_info.value.as_dict()
    assert error["code"] == "cad_invalid_extension"
    assert error["details"]["actual_extension"] == ".txt"


def test_empty_step_file_raises_read_error(tmp_path: Path) -> None:
    empty_step = tmp_path / "empty.step"
    empty_step.write_text("", encoding="utf-8")

    with pytest.raises(StepReadError) as exc_info:
        StepReader().parse(empty_step)

    assert exc_info.value.as_dict()["code"] == "step_read_failed"


def test_generated_box_step_parses_to_expected_geometry(tmp_path: Path) -> None:
    box_step = tmp_path / "box.step"
    _write_box_step(box_step)

    result = StepReader().parse(box_step)

    assert isinstance(result, StepParseResult)
    assert result.schema_version == "1.0"
    assert result.file.source_name == "box.step"
    assert result.diagnostics.root_count > 0
    assert result.diagnostics.transferred_count > 0
    assert result.diagnostics.shape_count > 0
    assert result.diagnostics.canonical_unit == "MM"
    assert result.diagnostics.source_length_units == ["millimetre"]
    assert result.diagnostics.shape_kind == "single_solid"
    assert result.validity.is_valid is True
    assert result.topology.solids == 1
    assert result.topology.faces == 6
    assert result.bounding_box.size == pytest.approx([10.0, 20.0, 30.0], abs=1e-5)
    assert result.mass_properties.volume == pytest.approx(6000.0, abs=1e-5)
    assert result.mass_properties.surface_area == pytest.approx(2200.0, abs=1e-5)
    assert result.tolerance_summary.maximum >= result.tolerance_summary.minimum


def test_size_limit_is_configurable(tmp_path: Path) -> None:
    tiny_step = tmp_path / "tiny.step"
    tiny_step.write_text("ISO-10303-21;", encoding="utf-8")
    settings = Settings(cad_max_file_size_bytes=1)

    with pytest.raises(Exception) as exc_info:
        StepReader(settings).parse(tiny_step)

    assert getattr(exc_info.value, "code", None) == "cad_file_too_large"
