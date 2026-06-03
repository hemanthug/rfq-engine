from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.cad.errors import (
    CadFileMissingError,
    CadFileNotRegularError,
    CadFileTooLargeError,
    CadInvalidExtensionError,
    StepNullShapeError,
    StepReadError,
    StepTransferError,
    StepUnsupportedShapeError,
)
from app.cad.shape_analysis import (
    check_shape_validity,
    classify_shape,
    compute_bounding_box,
    compute_mass_properties,
    count_topology,
    summarize_tolerances,
)
from app.config import Settings, get_settings
from app.schemas.cad import CadFileMetadata, StepImportDiagnostics, StepParseResult


PARSER_VERSION = "step_reader_v1"


@dataclass(frozen=True)
class StepShapeContext:
    shape: Any
    parse_result: StepParseResult


def _import_step_modules() -> dict[str, Any]:
    import OCC
    from OCC.Core.IFSelect import IFSelect_RetDone
    from OCC.Core.Interface import Interface_Static
    from OCC.Core.STEPControl import STEPControl_Reader
    from OCC.Core.TColStd import TColStd_SequenceOfAsciiString

    return {
        "OCC": OCC,
        "IFSelect_RetDone": IFSelect_RetDone,
        "Interface_Static": Interface_Static,
        "STEPControl_Reader": STEPControl_Reader,
        "TColStd_SequenceOfAsciiString": TColStd_SequenceOfAsciiString,
    }


def _status_name(status: Any) -> str:
    name = getattr(status, "name", None)
    if name:
        return str(name)
    return str(status)


def _sequence_to_list(sequence: Any) -> list[str]:
    values: list[str] = []
    for index in range(1, int(sequence.Length()) + 1):
        value = sequence.Value(index)
        if hasattr(value, "ToCString"):
            values.append(str(value.ToCString()))
        else:
            values.append(str(value))
    return values


class StepReader:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def parse(self, path: str | Path) -> StepParseResult:
        return self.load_context(path).parse_result

    def load_context(self, path: str | Path) -> StepShapeContext:
        step_path = self._validate_path(path)
        modules = _import_step_modules()

        reader = modules["STEPControl_Reader"]()
        read_status = reader.ReadFile(str(step_path))
        read_status_name = _status_name(read_status)
        if read_status != modules["IFSelect_RetDone"]:
            raise StepReadError(
                "STEP reader failed to load the file.",
                step_path,
                read_status=read_status_name,
            )

        source_length_units, source_angle_units, source_solid_angle_units = self._file_units(reader, modules)
        root_count = int(reader.NbRootsForTransfer())
        if root_count <= 0:
            raise StepTransferError("STEP file has no transferable roots.", step_path, root_count=root_count)

        transferred_count = int(reader.TransferRoots())
        if transferred_count <= 0:
            raise StepTransferError(
                "STEP transfer produced no shapes.",
                step_path,
                root_count=root_count,
                transferred_count=transferred_count,
            )

        shape_count = int(reader.NbShapes())
        shape = reader.OneShape()
        if shape.IsNull():
            raise StepNullShapeError("STEP transfer produced a null aggregate shape.", step_path)

        topology = count_topology(shape)
        shape_kind = classify_shape(topology)
        warnings = self._warnings(shape_kind, topology)

        if self.settings.cad_strict_solid and topology.solids < 1:
            raise StepUnsupportedShapeError(
                "STEP output does not contain a solid shape.",
                step_path,
                shape_kind=shape_kind,
                topology=topology.model_dump(),
            )

        validity = check_shape_validity(shape)
        if not validity.is_valid:
            warnings.append("shape_invalid")

        mass_properties = compute_mass_properties(shape)
        if mass_properties.volume <= 0:
            warnings.append("zero_or_negative_volume")
        if topology.solids > 1:
            warnings.append("multi_solid_output")
        if not source_length_units:
            warnings.append("source_length_units_not_reported")
        elif len(set(source_length_units)) > 1:
            warnings.append("multiple_source_length_units")

        canonical_unit = str(modules["Interface_Static"].CVal("xstep.cascade.unit"))
        diagnostics = StepImportDiagnostics(
            parser_version=PARSER_VERSION,
            pythonocc_version=str(getattr(modules["OCC"], "VERSION", "unknown")),
            canonical_unit=canonical_unit or self.settings.cad_canonical_unit,
            source_length_units=source_length_units,
            source_angle_units=source_angle_units,
            source_solid_angle_units=source_solid_angle_units,
            read_status=read_status_name,
            root_count=root_count,
            transferred_count=transferred_count,
            shape_count=shape_count,
            shape_kind=shape_kind,
            strict_solid=self.settings.cad_strict_solid,
            warnings=sorted(set(warnings)),
        )

        parse_result = StepParseResult(
            schema_version="1.0",
            file=CadFileMetadata(
                source_path=str(step_path),
                source_name=step_path.name,
                size_bytes=step_path.stat().st_size,
            ),
            diagnostics=diagnostics,
            validity=validity,
            bounding_box=compute_bounding_box(shape),
            mass_properties=mass_properties,
            tolerance_summary=summarize_tolerances(shape),
            topology=topology,
        )
        return StepShapeContext(shape=shape, parse_result=parse_result)

    def _validate_path(self, path: str | Path) -> Path:
        step_path = Path(path).resolve()
        if not step_path.exists():
            raise CadFileMissingError("CAD file does not exist.", step_path)
        if not step_path.is_file():
            raise CadFileNotRegularError("CAD path is not a regular file.", step_path)
        if step_path.suffix.lower() not in self.settings.cad_allowed_extensions:
            raise CadInvalidExtensionError(
                "CAD file extension is not supported.",
                step_path,
                allowed_extensions=list(self.settings.cad_allowed_extensions),
                actual_extension=step_path.suffix.lower(),
            )

        size_bytes = step_path.stat().st_size
        if size_bytes > self.settings.cad_max_file_size_bytes:
            raise CadFileTooLargeError(
                "CAD file exceeds the configured parser size limit.",
                step_path,
                size_bytes=size_bytes,
                max_file_size_bytes=self.settings.cad_max_file_size_bytes,
            )
        return step_path

    def _file_units(self, reader: Any, modules: dict[str, Any]) -> tuple[list[str], list[str], list[str]]:
        sequence_type = modules["TColStd_SequenceOfAsciiString"]
        length_units = sequence_type()
        angle_units = sequence_type()
        solid_angle_units = sequence_type()
        reader.FileUnits(length_units, angle_units, solid_angle_units)
        return (
            _sequence_to_list(length_units),
            _sequence_to_list(angle_units),
            _sequence_to_list(solid_angle_units),
        )

    def _warnings(self, shape_kind: str, topology: Any) -> list[str]:
        warnings: list[str] = []
        if shape_kind != "single_solid":
            warnings.append(f"shape_kind_{shape_kind}")
        if topology.faces == 0:
            warnings.append("no_faces")
        return warnings
