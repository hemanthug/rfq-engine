from __future__ import annotations

from pydantic import BaseModel

from app.schemas.preview import PreviewMeshResult
from app.schemas.pricing import CncPricingResult, MoldingPricingResult, SheetMetalPricingResult


class QuoteUploadMetadata(BaseModel):
    filename: str
    size_bytes: int
    extension: str


class QuoteWorkflowMetadata(BaseModel):
    schema_version: str
    elapsed_ms: float


class QuoteWorkflowResult(BaseModel):
    quote: CncPricingResult
    preview: PreviewMeshResult
    upload: QuoteUploadMetadata
    workflow: QuoteWorkflowMetadata


class MoldingQuoteWorkflowResult(BaseModel):
    quote: MoldingPricingResult
    preview: PreviewMeshResult
    upload: QuoteUploadMetadata
    workflow: QuoteWorkflowMetadata


class SheetMetalQuoteWorkflowResult(BaseModel):
    quote: SheetMetalPricingResult
    preview: PreviewMeshResult
    upload: QuoteUploadMetadata
    workflow: QuoteWorkflowMetadata


class ApiErrorResponse(BaseModel):
    code: str
    message: str
    details: dict = {}
