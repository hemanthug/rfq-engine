from __future__ import annotations

from pydantic import BaseModel

from app.schemas.cad import BoundingBox, StepParseResult
from app.schemas.recommendations import ProcessFitResult


class PreviewMeshQuality(BaseModel):
    linear_deflection_mm: float
    angular_deflection_rad: float
    is_relative: bool
    is_parallel: bool


class PreviewMeshResult(BaseModel):
    schema_version: str
    units: str
    positions: list[float]
    normals: list[float]
    indices: list[int]
    edges: list[float]
    bbox: BoundingBox
    triangle_count: int
    vertex_count: int
    mesh_quality: PreviewMeshQuality


class CadPreviewUploadMetadata(BaseModel):
    filename: str
    size_bytes: int
    extension: str


class CadPreviewWorkflowMetadata(BaseModel):
    schema_version: str
    elapsed_ms: float


class CadPreviewWorkflowResult(BaseModel):
    preview: PreviewMeshResult
    source: StepParseResult
    process_fit: ProcessFitResult | None = None
    upload: CadPreviewUploadMetadata
    workflow: CadPreviewWorkflowMetadata
