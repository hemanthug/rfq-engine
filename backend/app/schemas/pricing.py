from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.schemas.features import FeatureExtractionResult
from app.schemas.recommendations import CavityRecommendationResult


class CncPricingRequest(BaseModel):
    material: str
    quantity: int = Field(gt=0)
    tolerance_class: str
    finish: str
    lead_time_class: str
    notes: str | None = None


class PricingLineItem(BaseModel):
    code: str
    label: str
    amount: float
    basis: str
    details: dict[str, Any] = Field(default_factory=dict)


class CncPricingDiagnostics(BaseModel):
    pricing_version: str
    rate_card_version: str
    rate_card_kind: str
    geometry_signals: dict[str, float]
    missing_or_inferred_values: list[str]


class CncPricingResult(BaseModel):
    schema_version: str
    process: str
    currency: str
    source: FeatureExtractionResult
    request: CncPricingRequest
    line_items: list[PricingLineItem]
    subtotal: float
    unit_price: float
    quantity: int
    confidence: float
    warnings: list[str]
    assumptions: list[str]
    diagnostics: CncPricingDiagnostics


class MoldingPricingRequest(BaseModel):
    material: str
    quantity: int = Field(gt=0)
    annual_volume: int = Field(gt=0)
    cavities: int | None = None
    mold_class: str
    finish: str
    lead_time_class: str
    notes: str | None = None

    @field_validator("cavities")
    @classmethod
    def validate_cavities(cls, value: int | None) -> int | None:
        if value is None:
            return value
        if value not in {1, 2, 4, 8}:
            raise ValueError("cavities must be one of 1, 2, 4, 8, or auto")
        return value


class MoldingPricingDiagnostics(BaseModel):
    pricing_version: str
    rate_card_version: str
    rate_card_kind: str
    geometry_signals: dict[str, float]
    effective_amortized_unit_price: float
    cavity_recommendation: CavityRecommendationResult
    missing_or_inferred_values: list[str]


class MoldingPricingResult(BaseModel):
    schema_version: str
    process: str
    currency: str
    source: FeatureExtractionResult
    request: MoldingPricingRequest
    tooling_line_items: list[PricingLineItem]
    production_line_items: list[PricingLineItem]
    tooling_cost: float
    production_subtotal: float
    unit_price: float
    total_first_order_cost: float
    quantity: int
    confidence: float
    warnings: list[str]
    assumptions: list[str]
    diagnostics: MoldingPricingDiagnostics


class SheetMetalPricingRequest(BaseModel):
    material: str
    quantity: int = Field(gt=0)
    finish: str
    lead_time_class: str
    notes: str | None = None


class SheetMetalPricingDiagnostics(BaseModel):
    pricing_version: str
    rate_card_version: str
    rate_card_kind: str
    geometry_signals: dict[str, Any]
    missing_or_inferred_values: list[str]


class SheetMetalPricingResult(BaseModel):
    schema_version: str
    process: str
    currency: str
    source: FeatureExtractionResult
    request: SheetMetalPricingRequest
    line_items: list[PricingLineItem]
    subtotal: float
    unit_price: float
    quantity: int
    confidence: float
    warnings: list[str]
    assumptions: list[str]
    diagnostics: SheetMetalPricingDiagnostics
