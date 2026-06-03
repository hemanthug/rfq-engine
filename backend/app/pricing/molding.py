from __future__ import annotations

from app.pricing.molding_rate_card import MoldingRateCard, get_default_molding_rate_card
from app.schemas.features import FeatureExtractionResult
from app.schemas.pricing import MoldingPricingDiagnostics, MoldingPricingRequest, MoldingPricingResult, PricingLineItem
from app.schemas.recommendations import CavityCandidateResult, CavityRecommendationResult


PRICING_VERSION = "injection_molding_budgetary_pricer_v1"
PROFILE_COMPLEXITY_REASONS = {
    "tooth_root_cylindrical_arc",
    "external_profile_cylindrical_flank",
}
CAVITY_OPTIONS = [1, 2, 4, 8]
CAVITY_CLASS_CAPS = {
    "prototype": 1,
    "bridge": 2,
    "production": 4,
    "high_volume": 8,
}
CAVITY_MIN_ANNUAL_VOLUME = {
    1: 1,
    2: 7500,
    4: 30000,
    8: 100000,
}
CAVITY_LAYOUT_AREA_LIMIT_CM2 = {
    "prototype": 250.0,
    "bridge": 500.0,
    "production": 900.0,
    "high_volume": 1400.0,
}


class MoldingBudgetaryPricer:
    def __init__(self, rate_card: MoldingRateCard | None = None) -> None:
        self.rate_card = rate_card or get_default_molding_rate_card()

    def price(self, features: FeatureExtractionResult, request: MoldingPricingRequest) -> MoldingPricingResult:
        material = self.rate_card.material(request.material)
        mold_class = self.rate_card.mold_class(request.mold_class)
        finish = self.rate_card.finish(request.finish)
        lead_time = self.rate_card.lead_time(request.lead_time_class)
        annual_volume_tier = self.rate_card.annual_volume_tier(request.annual_volume)
        cavity_recommendation = self._recommend_cavities(
            features=features,
            request=request,
            material=material,
            mold_class=mold_class,
            finish=finish,
            lead_time=lead_time,
            annual_volume_multiplier=annual_volume_tier.production_multiplier,
        )
        selected_cavities = request.cavities or cavity_recommendation.recommended_cavities
        effective_request = request.model_copy(update={"cavities": selected_cavities})

        geometry = self._geometry_signals(features, material, selected_cavities)
        warnings = self._warnings(features)
        warnings.extend(mold_class.warnings)
        warnings.extend(finish.warnings)
        warnings.extend(lead_time.warnings)
        warnings.extend(annual_volume_tier.warnings)
        if mold_class.max_shots is not None and request.annual_volume > mold_class.max_shots:
            warnings.append("annual_volume_exceeds_selected_mold_class_life")

        tooling_line_items = self._tooling_line_items(geometry, mold_class, finish, lead_time, selected_cavities)
        production_line_items = self._production_line_items(
            geometry=geometry,
            material=material,
            finish=finish,
            annual_volume_multiplier=annual_volume_tier.production_multiplier,
            quantity=effective_request.quantity,
        )

        production_before_minimum = sum(item.amount for item in production_line_items)
        minimum_adjustment = max(0.0, self.rate_card.shop_rates.minimum_production_order_usd - production_before_minimum)
        production_line_items.append(
            PricingLineItem(
                code="minimum_production_order_adjustment",
                label="Minimum production order adjustment",
                amount=_money(minimum_adjustment),
                basis="rate-card production minimum floor",
                details={"minimum_production_order_usd": self.rate_card.shop_rates.minimum_production_order_usd},
            )
        )

        tooling_cost = _money(sum(item.amount for item in tooling_line_items))
        production_subtotal = _money(sum(item.amount for item in production_line_items))
        total_first_order_cost = _money(tooling_cost + production_subtotal)
        effective_unit = _money(total_first_order_cost / effective_request.quantity)

        return MoldingPricingResult(
            schema_version="1.0",
            process=self.rate_card.process,
            currency=self.rate_card.currency,
            source=features,
            request=effective_request,
            tooling_line_items=tooling_line_items,
            production_line_items=production_line_items,
            tooling_cost=tooling_cost,
            production_subtotal=production_subtotal,
            unit_price=_money(production_subtotal / effective_request.quantity),
            total_first_order_cost=total_first_order_cost,
            quantity=effective_request.quantity,
            confidence=self._confidence(features, warnings),
            warnings=sorted(set(warnings)),
            assumptions=[
                "budgetary_estimate_not_binding",
                "dfm_not_performed",
                "moldflow_not_performed",
                "parting_line_and_undercuts_not_analyzed",
                "tool_design_not_generated",
                "cycle_time_estimated_from_geometry",
                "material_properties_from_rate_card",
                "single_material_single_part_quote",
            ],
            diagnostics=MoldingPricingDiagnostics(
                pricing_version=PRICING_VERSION,
                rate_card_version=self.rate_card.version,
                rate_card_kind=self.rate_card.kind,
                geometry_signals=geometry,
                effective_amortized_unit_price=effective_unit,
                cavity_recommendation=cavity_recommendation,
                missing_or_inferred_values=[
                    "wall_thickness_not_measured",
                    "parting_line_not_selected",
                    "gate_location_not_selected",
                    "runner_sprue_system_not_designed",
                    "moldflow_not_performed",
                    "cycle_time_estimated",
                ],
            ),
        )

    def _recommend_cavities(
        self,
        features: FeatureExtractionResult,
        request: MoldingPricingRequest,
        material: object,
        mold_class: object,
        finish: object,
        lead_time: object,
        annual_volume_multiplier: float,
    ) -> CavityRecommendationResult:
        candidate_results: list[CavityCandidateResult] = []
        for cavities in CAVITY_OPTIONS:
            rejection_reasons = self._cavity_rejection_reasons(features, request, cavities)
            if rejection_reasons:
                candidate_results.append(
                    CavityCandidateResult(
                        cavities=cavities,
                        feasible=False,
                        rejection_reasons=rejection_reasons,
                    )
                )
                continue

            totals = self._cavity_candidate_totals(
                features=features,
                request=request,
                material=material,
                mold_class=mold_class,
                finish=finish,
                lead_time=lead_time,
                annual_volume_multiplier=annual_volume_multiplier,
                cavities=cavities,
            )
            candidate_results.append(
                CavityCandidateResult(
                    cavities=cavities,
                    feasible=True,
                    effective_amortized_unit_price=totals["effective_amortized_unit_price"],
                    tooling_cost=totals["tooling_cost"],
                    production_subtotal=totals["production_subtotal"],
                    estimated_cycle_seconds=totals["estimated_cycle_seconds"],
                    rejection_reasons=[],
                )
            )

        feasible = [candidate for candidate in candidate_results if candidate.feasible]
        selected = feasible[0]
        for candidate in feasible[1:]:
            if (
                candidate.effective_amortized_unit_price is not None
                and selected.effective_amortized_unit_price is not None
                and candidate.effective_amortized_unit_price < selected.effective_amortized_unit_price * 0.97
            ):
                selected = candidate
        if request.cavities is not None:
            selected = next(candidate for candidate in candidate_results if candidate.cavities == request.cavities)

        if request.cavities is not None:
            reason = f"User selected {request.cavities} cavity/cavities; recommendation diagnostics retained."
            confidence = "high"
        elif selected.cavities == 1:
            reason = "Single-cavity tooling is the conservative economic fit for this request."
            confidence = "medium"
        else:
            reason = (
                f"{selected.cavities} cavities reduce amortized unit cost by at least 3% "
                "within conservative mold-layout gates."
            )
            confidence = "medium"

        return CavityRecommendationResult(
            recommended_cavities=selected.cavities,
            user_overrode_cavities=request.cavities is not None,
            candidate_cavity_results=candidate_results,
            cavity_recommendation_reason=reason,
            cavity_recommendation_confidence=confidence,
            details={
                "annual_volume": request.annual_volume,
                "quantity": request.quantity,
                "mold_class": request.mold_class,
                "improvement_required_to_step_up": 0.03,
            },
        )

    def _cavity_rejection_reasons(
        self,
        features: FeatureExtractionResult,
        request: MoldingPricingRequest,
        cavities: int,
    ) -> list[str]:
        geometry = self._geometry_signals(features, self.rate_card.material(request.material), cavities)
        reasons: list[str] = []
        if cavities > CAVITY_CLASS_CAPS[request.mold_class]:
            reasons.append("exceeds_mold_class_cavity_cap")
        if request.annual_volume < CAVITY_MIN_ANNUAL_VOLUME[cavities]:
            reasons.append("annual_volume_too_low_for_cavity_count")
        layout_area = geometry["projected_area_cm2"] * cavities * 1.8
        if layout_area > CAVITY_LAYOUT_AREA_LIMIT_CM2[request.mold_class]:
            reasons.append("layout_projected_area_too_large_for_mold_class")
        if cavities > 1 and geometry["max_dimension_mm"] > 180.0:
            reasons.append("part_too_large_for_budgetary_multi_cavity_layout")
        if cavities > 4 and geometry["max_dimension_mm"] > 120.0:
            reasons.append("part_too_large_for_budgetary_eight_cavity_layout")
        return reasons

    def _cavity_candidate_totals(
        self,
        features: FeatureExtractionResult,
        request: MoldingPricingRequest,
        material: object,
        mold_class: object,
        finish: object,
        lead_time: object,
        annual_volume_multiplier: float,
        cavities: int,
    ) -> dict[str, float]:
        geometry = self._geometry_signals(features, material, cavities)
        tooling = self._tooling_line_items(geometry, mold_class, finish, lead_time, cavities)
        production = self._production_line_items(
            geometry=geometry,
            material=material,
            finish=finish,
            annual_volume_multiplier=annual_volume_multiplier,
            quantity=request.quantity,
        )
        production_before_minimum = sum(item.amount for item in production)
        minimum_adjustment = max(0.0, self.rate_card.shop_rates.minimum_production_order_usd - production_before_minimum)
        tooling_cost = _money(sum(item.amount for item in tooling))
        production_subtotal = _money(production_before_minimum + minimum_adjustment)
        production_unit_price = production_subtotal / request.quantity
        return {
            "tooling_cost": tooling_cost,
            "production_subtotal": production_subtotal,
            "estimated_cycle_seconds": geometry["estimated_cycle_seconds"],
            "effective_amortized_unit_price": _money(production_unit_price + tooling_cost / request.annual_volume),
        }

    def _geometry_signals(
        self,
        features: FeatureExtractionResult,
        material: object,
        cavities: int,
    ) -> dict[str, float]:
        bbox_size = features.source.bounding_box.size
        bbox_pairs = [
            bbox_size[0] * bbox_size[1],
            bbox_size[0] * bbox_size[2],
            bbox_size[1] * bbox_size[2],
        ]
        volume_mm3 = max(0.0, features.source.mass_properties.volume)
        surface_area_mm2 = max(1.0, features.source.mass_properties.surface_area)
        wall_proxy_mm = _clamp((2.0 * volume_mm3) / surface_area_mm2, 0.5, 8.0)
        profile_count = self._profile_complexity_candidate_count(features)
        complexity_score = float(features.complexity.score)
        tool_complexity_multiplier = 1.0 + (complexity_score / 100.0) * (
            self.rate_card.defaults.tool_complexity_multiplier_at_100 - 1.0
        )
        cycle_complexity_multiplier = 1.0 + (complexity_score / 100.0) * (
            self.rate_card.defaults.cycle_complexity_multiplier_at_100 - 1.0
        )
        profile_complexity_multiplier = min(1.4, 1.0 + profile_count * 0.002)
        cycle_seconds = (
            (
                self.rate_card.defaults.base_cycle_seconds
                + wall_proxy_mm * self.rate_card.defaults.cooling_seconds_per_mm_wall_proxy
                + self.rate_card.defaults.handling_seconds_per_part
            )
            * material.processing_multiplier
            * cycle_complexity_multiplier
            * profile_complexity_multiplier
            / max(1, cavities)
        )

        return {
            "bbox_x_mm": float(bbox_size[0]),
            "bbox_y_mm": float(bbox_size[1]),
            "bbox_z_mm": float(bbox_size[2]),
            "max_dimension_mm": float(max(bbox_size)),
            "part_volume_cm3": float(volume_mm3 / 1000.0),
            "surface_area_cm2": float(surface_area_mm2 / 100.0),
            "projected_area_cm2": float(max(bbox_pairs) / 100.0),
            "wall_proxy_mm": float(wall_proxy_mm),
            "part_mass_kg": float((volume_mm3 / 1000.0) * material.density_g_cm3 / 1000.0),
            "complexity_score": complexity_score,
            "profile_complexity_candidate_count": float(profile_count),
            "profile_complexity_multiplier": float(round(profile_complexity_multiplier, 3)),
            "tool_complexity_multiplier": float(round(tool_complexity_multiplier, 3)),
            "cycle_complexity_multiplier": float(round(cycle_complexity_multiplier, 3)),
            "estimated_cycle_seconds": float(round(cycle_seconds, 3)),
            "face_count": float(len(features.faces)),
            "edge_count": float(len(features.edges)),
            "cavities": float(cavities),
        }

    def _tooling_line_items(
        self,
        geometry: dict[str, float],
        mold_class: object,
        finish: object,
        lead_time: object,
        cavities: int,
    ) -> list[PricingLineItem]:
        base_tooling = mold_class.base_tooling_usd * mold_class.tooling_multiplier
        size_factor = min(1.8, 1.0 + max(0.0, geometry["max_dimension_mm"] - 80.0) / 200.0)
        base_amount = base_tooling * size_factor * lead_time.multiplier
        complexity_amount = base_amount * (geometry["tool_complexity_multiplier"] - 1.0)
        cavity_amount = base_tooling * max(0, cavities - 1) * 0.18

        return [
            PricingLineItem(
                code="mold_base_tooling",
                label=f"Mold base/tooling: {mold_class.label}",
                amount=_money(base_amount),
                basis="mold-class base tooling, size factor, and lead-time multiplier",
                details={
                    "base_tooling_usd": mold_class.base_tooling_usd,
                    "mold_class_multiplier": mold_class.tooling_multiplier,
                    "size_factor": round(size_factor, 3),
                    "lead_time_multiplier": lead_time.multiplier,
                },
            ),
            PricingLineItem(
                code="cavity_layout_adjustment",
                label="Cavity/layout adjustment",
                amount=_money(cavity_amount),
                basis="additional cavity layout allowance",
                details={"cavities": cavities, "additional_cavity_multiplier_each": 0.18},
            ),
            PricingLineItem(
                code="geometry_complexity_adjustment",
                label="Geometry complexity adjustment",
                amount=_money(complexity_amount),
                basis="STEP-derived complexity score and rejected profile candidates",
                details={
                    "complexity_score": geometry["complexity_score"],
                    "tool_complexity_multiplier": geometry["tool_complexity_multiplier"],
                    "profile_complexity_candidate_count": int(geometry["profile_complexity_candidate_count"]),
                },
            ),
            PricingLineItem(
                code="finish_texture_adjustment",
                label=f"Finish/texture: {finish.label}",
                amount=_money(finish.tooling_add_usd),
                basis="tool finish or texture allowance from rate card",
                details={"tooling_add_usd": finish.tooling_add_usd},
            ),
        ]

    def _production_line_items(
        self,
        geometry: dict[str, float],
        material: object,
        finish: object,
        annual_volume_multiplier: float,
        quantity: int,
    ) -> list[PricingLineItem]:
        resin_amount = (
            geometry["part_mass_kg"]
            * self.rate_card.defaults.scrap_factor
            * material.resin_usd_per_kg
            * quantity
        )
        cycle_seconds = (
            geometry["estimated_cycle_seconds"]
            * finish.production_multiplier
            * annual_volume_multiplier
        )
        press_amount = cycle_seconds * quantity / 3600.0 * self.rate_card.shop_rates.press_hourly_usd
        setup_amount = self.rate_card.defaults.setup_changeover_hours * self.rate_card.shop_rates.setup_hourly_usd
        handling_amount = (
            self.rate_card.defaults.handling_seconds_per_part
            * quantity
            / 3600.0
            * self.rate_card.shop_rates.handling_qc_hourly_usd
        )

        return [
            PricingLineItem(
                code="resin_material",
                label=f"Resin material: {material.label}",
                amount=_money(resin_amount),
                basis="part volume, density, resin price, quantity, and scrap factor",
                details={
                    "part_mass_kg": geometry["part_mass_kg"],
                    "resin_usd_per_kg": material.resin_usd_per_kg,
                    "scrap_factor": self.rate_card.defaults.scrap_factor,
                    "quantity": quantity,
                },
            ),
            PricingLineItem(
                code="press_time",
                label="Machine/press time",
                amount=_money(press_amount),
                basis="estimated cycle time, cavity count, process multipliers, and press hourly rate",
                details={
                    "estimated_cycle_seconds": cycle_seconds,
                    "base_estimated_cycle_seconds": geometry["estimated_cycle_seconds"],
                    "finish_multiplier": finish.production_multiplier,
                    "annual_volume_multiplier": annual_volume_multiplier,
                    "profile_complexity_candidate_count": int(geometry["profile_complexity_candidate_count"]),
                    "profile_complexity_multiplier": geometry["profile_complexity_multiplier"],
                    "press_hourly_usd": self.rate_card.shop_rates.press_hourly_usd,
                    "quantity": quantity,
                },
            ),
            PricingLineItem(
                code="setup_changeover",
                label="Setup/changeover",
                amount=_money(setup_amount),
                basis="rate-card setup/changeover hours",
                details={
                    "setup_changeover_hours": self.rate_card.defaults.setup_changeover_hours,
                    "setup_hourly_usd": self.rate_card.shop_rates.setup_hourly_usd,
                },
            ),
            PricingLineItem(
                code="handling_qc",
                label="Handling/QC",
                amount=_money(handling_amount),
                basis="per-part handling and QC allowance",
                details={
                    "handling_seconds_per_part": self.rate_card.defaults.handling_seconds_per_part,
                    "handling_qc_hourly_usd": self.rate_card.shop_rates.handling_qc_hourly_usd,
                    "quantity": quantity,
                },
            ),
        ]

    def _warnings(self, features: FeatureExtractionResult) -> list[str]:
        warnings = [
            "budgetary_estimate_not_binding",
            "dfm_not_performed",
            "moldflow_not_performed",
            "tooling_requires_engineering_review",
            "parting_line_and_undercuts_not_analyzed",
        ]
        warnings.extend(features.diagnostics.warnings)
        if features.complexity.score >= 70:
            warnings.append("high_complexity_geometry_budgetary_confidence_reduced")
        if self._profile_complexity_candidate_count(features) > 0:
            warnings.append("profile_geometry_priced_as_molding_complexity")
        return warnings

    def _confidence(self, features: FeatureExtractionResult, warnings: list[str]) -> float:
        confidence = 0.58
        if features.complexity.score >= 70:
            confidence -= 0.12
        elif features.complexity.score >= 45:
            confidence -= 0.06
        confidence -= min(0.10, len(features.diagnostics.warnings) * 0.02)
        if any("review" in warning for warning in warnings):
            confidence -= 0.05
        return round(max(0.25, min(0.72, confidence)), 2)

    def _profile_complexity_candidate_count(self, features: FeatureExtractionResult) -> int:
        return sum(
            1
            for candidate in features.diagnostics.rejected_candidates
            if candidate.reason in PROFILE_COMPLEXITY_REASONS
        )


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _money(value: float) -> float:
    return round(float(value) + 0.0, 2)
