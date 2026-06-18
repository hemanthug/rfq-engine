from __future__ import annotations

from app.pricing.rate_card import CncRateCard, get_default_rate_card
from app.schemas.features import FeatureExtractionResult
from app.schemas.pricing import CncPricingDiagnostics, CncPricingRequest, CncPricingResult, PricingLineItem


PRICING_VERSION = "cnc_budgetary_pricer_v2"
PROFILE_COMPLEXITY_REASONS = {
    "tooth_root_cylindrical_arc",
    "external_profile_cylindrical_flank",
}


class CncBudgetaryPricer:
    def __init__(self, rate_card: CncRateCard | None = None) -> None:
        self.rate_card = rate_card or get_default_rate_card()

    def price(self, features: FeatureExtractionResult, request: CncPricingRequest) -> CncPricingResult:
        material = self.rate_card.material(request.material)
        tolerance = self.rate_card.tolerance(request.tolerance_class)
        finish = self.rate_card.finish(request.finish)
        lead_time = self.rate_card.lead_time(request.lead_time_class)
        quantity_tier = self.rate_card.quantity_tier(request.quantity)

        geometry = self._geometry_signals(features, material)

        assumptions = [
            "budgetary_estimate_not_binding",
            "cnc_3_axis_milling_only",
            "pricing_uses_pre_cam_geometry_estimates",
            "stock_pricing_uses_bounding_box_allowance",
            "setup_orientation_not_analyzed",
            "threads_not_detected",
            "counterbores_countersinks_not_detected",
            "material_properties_from_rate_card",
        ]

        line_items: list[PricingLineItem] = []
        line_items.append(self._material_line_item(geometry, material, request.quantity))
        line_items.append(self._setup_line_item(features, request.quantity))
        line_items.append(self._machine_time_line_item(geometry, material, tolerance, request.quantity))
        line_items.append(self._feature_ops_line_item(features, request.quantity))
        line_items.append(self._tooling_line_item(request.quantity))
        line_items.append(self._deburr_qc_line_item(request.quantity))

        subtotal_before_adjustments = sum(item.amount for item in line_items)

        finish_amount = (
            subtotal_before_adjustments * (finish.multiplier - 1.0)
            + finish.per_part_add_usd * request.quantity
        )
        line_items.append(
            PricingLineItem(
                code="finish",
                label=f"Finish: {finish.label}",
                amount=_money(finish_amount),
                basis="finish multiplier and per-part add from rate card",
                details={
                    "finish": request.finish,
                    "multiplier": finish.multiplier,
                    "per_part_add_usd": finish.per_part_add_usd,
                    "quantity": request.quantity,
                },
            )
        )

        subtotal_after_finish = sum(item.amount for item in line_items)
        tier_adjustment = subtotal_after_finish * (quantity_tier.multiplier - 1.0)
        line_items.append(
            PricingLineItem(
                code="quantity_tier_adjustment",
                label="Quantity tier adjustment",
                amount=_money(tier_adjustment),
                basis="rate-card tier multiplier applied after base process costs",
                details={
                    "quantity": request.quantity,
                    "tier_min_quantity": quantity_tier.min_quantity,
                    "tier_max_quantity": quantity_tier.max_quantity,
                    "multiplier": quantity_tier.multiplier,
                },
            )
        )

        subtotal_after_tier = sum(item.amount for item in line_items)
        lead_time_adjustment = subtotal_after_tier * (lead_time.multiplier - 1.0)
        line_items.append(
            PricingLineItem(
                code="lead_time_adjustment",
                label=f"Lead time: {lead_time.label}",
                amount=_money(lead_time_adjustment),
                basis="lead-time multiplier from rate card",
                details={"lead_time_class": request.lead_time_class, "multiplier": lead_time.multiplier},
            )
        )

        subtotal_before_minimum = sum(item.amount for item in line_items)
        minimum_adjustment = max(0.0, self.rate_card.shop_rates.minimum_order_usd - subtotal_before_minimum)
        line_items.append(
            PricingLineItem(
                code="minimum_order_adjustment",
                label="Minimum order adjustment",
                amount=_money(minimum_adjustment),
                basis="rate-card minimum order floor",
                details={"minimum_order_usd": self.rate_card.shop_rates.minimum_order_usd},
            )
        )

        subtotal = _money(sum(item.amount for item in line_items))
        return CncPricingResult(
            schema_version="1.0",
            process=self.rate_card.process,
            currency=self.rate_card.currency,
            source=features,
            request=request,
            line_items=line_items,
            subtotal=subtotal,
            unit_price=_money(subtotal / request.quantity),
            quantity=request.quantity,
            confidence=self._confidence(features, request),
            assumptions=assumptions,
            diagnostics=CncPricingDiagnostics(
                pricing_version=PRICING_VERSION,
                rate_card_version=self.rate_card.version,
                rate_card_kind=self.rate_card.kind,
                geometry_signals=geometry,
                missing_or_inferred_values=[
                    "stock_size_inferred_from_bounding_box",
                    "setup_count_not_analyzed",
                    "toolpaths_not_generated",
                    "feeds_and_speeds_not_cam_validated",
                ],
            ),
        )

    def _geometry_signals(self, features: FeatureExtractionResult, material: object) -> dict[str, float]:
        allowance = self.rate_card.defaults.stock_allowance_mm_per_side
        bbox_size = features.source.bounding_box.size
        stock_size = [max(0.0, dimension + 2.0 * allowance) for dimension in bbox_size]
        stock_volume_mm3 = stock_size[0] * stock_size[1] * stock_size[2]
        part_volume_mm3 = max(0.0, features.source.mass_properties.volume)
        removed_volume_mm3 = max(0.0, stock_volume_mm3 - part_volume_mm3)
        stock_volume_cm3 = stock_volume_mm3 / 1000.0
        removed_volume_cm3 = removed_volume_mm3 / 1000.0
        surface_area_cm2 = max(0.0, features.source.mass_properties.surface_area) / 100.0
        stock_mass_kg = stock_volume_cm3 * material.density_g_cm3 / 1000.0

        return {
            "bbox_x_mm": float(bbox_size[0]),
            "bbox_y_mm": float(bbox_size[1]),
            "bbox_z_mm": float(bbox_size[2]),
            "stock_x_mm": float(stock_size[0]),
            "stock_y_mm": float(stock_size[1]),
            "stock_z_mm": float(stock_size[2]),
            "stock_volume_cm3": float(stock_volume_cm3),
            "part_volume_cm3": float(part_volume_mm3 / 1000.0),
            "removed_volume_cm3": float(removed_volume_cm3),
            "surface_area_cm2": float(surface_area_cm2),
            "stock_mass_kg": float(stock_mass_kg),
            "complexity_score": float(features.complexity.score),
            "hole_count": float(len(features.holes)),
            "through_hole_count": float(sum(1 for hole in features.holes if hole.hole_type == "through")),
            "blind_hole_count": float(sum(1 for hole in features.holes if hole.hole_type == "blind")),
            "pocket_count": float(len(features.pockets)),
            "face_count": float(len(features.faces)),
            "edge_count": float(len(features.edges)),
            "profile_complexity_candidate_count": float(self._profile_complexity_candidate_count(features)),
            "profile_complexity_multiplier": float(self._profile_complexity_multiplier(features)),
        }

    def _material_line_item(self, geometry: dict[str, float], material: object, quantity: int) -> PricingLineItem:
        material_per_part = geometry["stock_mass_kg"] * material.material_usd_per_kg * self.rate_card.defaults.scrap_factor
        return PricingLineItem(
            code="material",
            label=f"Raw stock: {material.label}",
            amount=_money(material_per_part * quantity),
            basis="bounding-box stock volume, density, material price, and scrap factor",
            details={
                "stock_mass_kg_per_part": geometry["stock_mass_kg"],
                "material_usd_per_kg": material.material_usd_per_kg,
                "scrap_factor": self.rate_card.defaults.scrap_factor,
                "quantity": quantity,
            },
        )

    def _setup_line_item(self, features: FeatureExtractionResult, quantity: int) -> PricingLineItem:
        setup_minutes = (
            self.rate_card.defaults.base_setup_programming_minutes
            + (features.complexity.score / 100.0) * self.rate_card.defaults.complexity_setup_minutes_at_100
        )
        amount = setup_minutes / 60.0 * self.rate_card.shop_rates.setup_hourly_usd
        return PricingLineItem(
            code="setup_programming",
            label="Setup and CAM programming",
            amount=_money(amount),
            basis="base setup minutes plus complexity minutes, amortized in unit price",
            details={
                "setup_minutes_total": setup_minutes,
                "setup_hourly_usd": self.rate_card.shop_rates.setup_hourly_usd,
                "quantity": quantity,
                "setup_usd_per_part": amount / quantity,
            },
        )

    def _machine_time_line_item(
        self,
        geometry: dict[str, float],
        material: object,
        tolerance: object,
        quantity: int,
    ) -> PricingLineItem:
        roughing_minutes = (
            geometry["removed_volume_cm3"]
            / material.material_removal_rate_cm3_min
            * material.machinability_multiplier
        )
        finishing_minutes = (
            geometry["surface_area_cm2"] / 100.0 * self.rate_card.defaults.finishing_minutes_per_100_cm2
        )
        minutes_per_part = (
            (roughing_minutes + finishing_minutes)
            * tolerance.multiplier
            * self._profile_complexity_multiplier_from_count(int(geometry["profile_complexity_candidate_count"]))
            * self.rate_card.defaults.pre_cam_overhead_multiplier
        )
        amount = minutes_per_part / 60.0 * self.rate_card.shop_rates.machine_hourly_usd * quantity
        return PricingLineItem(
            code="machine_time",
            label="Estimated 3-axis machine time",
            amount=_money(amount),
            basis="removed volume, finishing area, material MRR, tolerance, and pre-CAM overhead",
            details={
                "roughing_minutes_per_part": roughing_minutes,
                "finishing_minutes_per_part": finishing_minutes,
                "profile_complexity_candidate_count": int(geometry["profile_complexity_candidate_count"]),
                "profile_complexity_multiplier": geometry["profile_complexity_multiplier"],
                "estimated_cycle_minutes_per_part": minutes_per_part,
                "machine_hourly_usd": self.rate_card.shop_rates.machine_hourly_usd,
                "quantity": quantity,
            },
        )

    def _feature_ops_line_item(self, features: FeatureExtractionResult, quantity: int) -> PricingLineItem:
        through_holes = sum(1 for hole in features.holes if hole.hole_type == "through")
        blind_holes = sum(1 for hole in features.holes if hole.hole_type == "blind")
        pockets = len(features.pockets)
        per_part = (
            through_holes * self.rate_card.feature_operations.through_hole_usd_each
            + blind_holes * self.rate_card.feature_operations.blind_hole_usd_each
            + pockets * self.rate_card.feature_operations.pocket_usd_each
        )
        return PricingLineItem(
            code="feature_operations",
            label="Feature operations",
            amount=_money(per_part * quantity),
            basis="simple hole and pocket candidates from Phase 3 extraction",
            details={
                "through_holes": through_holes,
                "blind_holes": blind_holes,
                "pockets": pockets,
                "quantity": quantity,
            },
        )

    def _tooling_line_item(self, quantity: int) -> PricingLineItem:
        return PricingLineItem(
            code="tooling",
            label="Tooling allowance",
            amount=_money(self.rate_card.defaults.tooling_usd_per_part * quantity),
            basis="per-part tooling allowance from rate card",
            details={"tooling_usd_per_part": self.rate_card.defaults.tooling_usd_per_part, "quantity": quantity},
        )

    def _deburr_qc_line_item(self, quantity: int) -> PricingLineItem:
        minutes = self.rate_card.defaults.base_deburr_qc_minutes_per_part
        amount = minutes / 60.0 * self.rate_card.shop_rates.deburr_qc_hourly_usd * quantity
        return PricingLineItem(
            code="deburr_qc",
            label="Deburr and basic QC",
            amount=_money(amount),
            basis="per-part handling, deburr, and inspection allowance",
            details={
                "minutes_per_part": minutes,
                "deburr_qc_hourly_usd": self.rate_card.shop_rates.deburr_qc_hourly_usd,
                "quantity": quantity,
            },
        )

    def _confidence(self, features: FeatureExtractionResult, request: CncPricingRequest) -> float:
        confidence = 0.75
        if features.complexity.score >= 70:
            confidence -= 0.12
        elif features.complexity.score >= 45:
            confidence -= 0.06
        if request.tolerance_class == "tight":
            confidence -= 0.05
        elif request.tolerance_class == "precision":
            confidence -= 0.12
        if len(features.faces) > 50 or len(features.edges) > 120:
            confidence -= 0.08
        if request.tolerance_class == "precision":
            confidence -= 0.06
        return round(max(0.25, min(0.90, confidence)), 2)

    def _profile_complexity_candidate_count(self, features: FeatureExtractionResult) -> int:
        return sum(
            1
            for candidate in features.diagnostics.rejected_candidates
            if candidate.reason in PROFILE_COMPLEXITY_REASONS
        )

    def _profile_complexity_multiplier(self, features: FeatureExtractionResult) -> float:
        return self._profile_complexity_multiplier_from_count(self._profile_complexity_candidate_count(features))

    def _profile_complexity_multiplier_from_count(self, candidate_count: int) -> float:
        if candidate_count <= 0:
            return 1.0
        return round(min(2.25, 1.0 + candidate_count * 0.006), 3)


def _money(value: float) -> float:
    return round(float(value) + 0.0, 2)
