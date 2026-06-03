from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class RankedProcessRecommendation(BaseModel):
    process: str
    label: str
    score: float
    confidence: str
    reasons: list[str]
    warnings: list[str]


class ProcessFitResult(BaseModel):
    recommended_process: str
    ranked_processes: list[RankedProcessRecommendation]
    confidence: str
    reasons: list[str]
    warnings: list[str]
    signals: dict[str, float]


class CavityCandidateResult(BaseModel):
    cavities: int
    feasible: bool
    effective_amortized_unit_price: float | None = None
    tooling_cost: float | None = None
    production_subtotal: float | None = None
    estimated_cycle_seconds: float | None = None
    rejection_reasons: list[str]


class CavityRecommendationResult(BaseModel):
    recommended_cavities: int
    user_overrode_cavities: bool
    candidate_cavity_results: list[CavityCandidateResult]
    cavity_recommendation_reason: str
    cavity_recommendation_confidence: str
    details: dict[str, Any] = {}
