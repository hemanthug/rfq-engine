from pydantic import BaseModel, Field


class CadFileMetadata(BaseModel):
    source_path: str
    source_name: str
    size_bytes: int


class BoundingBox(BaseModel):
    minimum: list[float] = Field(min_length=3, max_length=3)
    maximum: list[float] = Field(min_length=3, max_length=3)
    size: list[float] = Field(min_length=3, max_length=3)


class MassProperties(BaseModel):
    volume: float
    surface_area: float


class ShapeValidity(BaseModel):
    is_valid: bool


class ToleranceSummary(BaseModel):
    minimum: float
    average: float
    maximum: float


class TopologyCounts(BaseModel):
    vertices: int
    edges: int
    wires: int
    faces: int
    shells: int
    solids: int
    comp_solids: int
    compounds: int


class StepImportDiagnostics(BaseModel):
    parser_version: str
    pythonocc_version: str
    canonical_unit: str
    source_length_units: list[str]
    source_angle_units: list[str]
    source_solid_angle_units: list[str]
    read_status: str
    root_count: int
    transferred_count: int
    shape_count: int
    shape_kind: str
    strict_solid: bool
    warnings: list[str]


class StepParseResult(BaseModel):
    schema_version: str
    file: CadFileMetadata
    diagnostics: StepImportDiagnostics
    validity: ShapeValidity
    bounding_box: BoundingBox
    mass_properties: MassProperties
    tolerance_summary: ToleranceSummary
    topology: TopologyCounts

