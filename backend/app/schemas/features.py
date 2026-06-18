from pydantic import BaseModel, Field

from app.schemas.cad import StepParseResult


class FaceAnalysis(BaseModel):
    face_id: str
    surface_type: str
    area: float
    tolerance: float
    edge_ids: list[str]
    inner_wire_count: int
    outer_wire_count: int
    normal: list[float] | None = Field(default=None, min_length=3, max_length=3)
    axis_origin: list[float] | None = Field(default=None, min_length=3, max_length=3)
    axis_direction: list[float] | None = Field(default=None, min_length=3, max_length=3)
    radius: float | None = None
    semi_angle: float | None = None


class EdgeAnalysis(BaseModel):
    edge_id: str
    curve_type: str
    length: float
    adjacent_face_ids: list[str]
    radius: float | None = None
    center: list[float] | None = Field(default=None, min_length=3, max_length=3)


class FaceAdjacency(BaseModel):
    edge_id: str
    face_ids: list[str]
    classification: str
    is_heuristic: bool = True


class HoleFeature(BaseModel):
    feature_id: str
    hole_type: str
    face_ids: list[str]
    diameter: float
    axis_origin: list[float] = Field(min_length=3, max_length=3)
    axis_direction: list[float] = Field(min_length=3, max_length=3)
    depth: float | None = None
    confidence: float
    evidence: list[str]


class PocketFeature(BaseModel):
    feature_id: str
    pocket_type: str
    bottom_face_id: str
    side_face_ids: list[str]
    depth: float | None = None
    confidence: float
    evidence: list[str]


class ComplexityScore(BaseModel):
    score: int = Field(ge=0, le=100)
    signals: dict[str, float]


class RejectedFeatureCandidate(BaseModel):
    candidate_type: str
    face_ids: list[str]
    reason: str
    evidence: list[str]


class FeatureDiagnostics(BaseModel):
    detector_versions: dict[str, str]
    deferred_feature_types: list[str]
    rejected_candidates: list[RejectedFeatureCandidate] = Field(default_factory=list)


class FeatureExtractionResult(BaseModel):
    schema_version: str
    source: StepParseResult
    faces: list[FaceAnalysis]
    edges: list[EdgeAnalysis]
    adjacency: list[FaceAdjacency]
    holes: list[HoleFeature]
    pockets: list[PocketFeature]
    complexity: ComplexityScore
    diagnostics: FeatureDiagnostics
