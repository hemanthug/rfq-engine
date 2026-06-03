from __future__ import annotations

from app.pricing.sheet_metal_rate_card import SheetMetalRateCard, get_default_sheet_metal_rate_card
from app.schemas.features import FeatureExtractionResult
from app.schemas.pricing import (
    PricingLineItem,
    SheetMetalPricingDiagnostics,
    SheetMetalPricingRequest,
    SheetMetalPricingResult,
)
from app.services.process_fit import sheet_metal_signals
from app.services.sheet_metal_geometry import (
    estimated_cut_length_mm,
    neutral_axis_unfold_metrics,
    raw_thin_shell_thickness_mm,
)


PRICING_VERSION = "sheet_metal_budgetary_pricer_v1"


class SheetMetalBudgetaryPricer:
    def __init__(self, rate_card: SheetMetalRateCard | None = None) -> None:
        self.rate_card = rate_card or get_default_sheet_metal_rate_card()

    def price(self, features: FeatureExtractionResult, request: SheetMetalPricingRequest) -> SheetMetalPricingResult:
        material = self.rate_card.material(request.material)
        finish = self.rate_card.finish(request.finish)
        lead_time = self.rate_card.lead_time(request.lead_time_class)
        quantity_tier = self.rate_card.quantity_tier(request.quantity)
        geometry = self._geometry_signals(features, material)

        warnings = self._warnings(features, geometry)
        warnings.extend(finish.warnings)
        warnings.extend(lead_time.warnings)
        warnings.extend(quantity_tier.warnings)

        line_items = [
            self._material_line_item(geometry, material, request.quantity),
            self._setup_line_item(),
            self._cutting_line_item(geometry, material, request.quantity),
            self._bend_line_item(geometry, request.quantity),
            self._deburr_qc_line_item(request.quantity),
        ]
        subtotal_before_finish = sum(item.amount for item in line_items)
        finish_amount = subtotal_before_finish * (finish.multiplier - 1.0) + finish.per_part_add_usd * request.quantity
        line_items.append(
            PricingLineItem(
                code="finish",
                label=f"Finish: {finish.label}",
                amount=_money(finish_amount),
                basis="finish multiplier and per-part add from sheet-metal rate card",
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
                basis="sheet-metal quantity tier multiplier",
                details={
                    "quantity": request.quantity,
                    "multiplier": quantity_tier.multiplier,
                    "tier_min_quantity": quantity_tier.min_quantity,
                    "tier_max_quantity": quantity_tier.max_quantity,
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
                basis="lead-time multiplier from sheet-metal rate card",
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
                basis="sheet-metal minimum order floor",
                details={"minimum_order_usd": self.rate_card.shop_rates.minimum_order_usd},
            )
        )

        subtotal = _money(sum(item.amount for item in line_items))
        return SheetMetalPricingResult(
            schema_version="1.0",
            process=self.rate_card.process,
            currency=self.rate_card.currency,
            source=features,
            request=request,
            line_items=line_items,
            subtotal=subtotal,
            unit_price=_money(subtotal / request.quantity),
            quantity=request.quantity,
            confidence=self._confidence(geometry, warnings),
            warnings=sorted(set(warnings)),
            assumptions=[
                "budgetary_estimate_not_binding",
                "flat_pattern_estimated_from_neutral_axis_unfold_metrics",
                "grain_direction_not_analyzed",
                "hardware_and_inserts_not_detected",
                "sheet_thickness_snapped_to_material_gauge_chart",
                "cut_length_estimated_from_topology_or_bounding_box",
            ],
            diagnostics=SheetMetalPricingDiagnostics(
                pricing_version=PRICING_VERSION,
                rate_card_version=self.rate_card.version,
                rate_card_kind=self.rate_card.kind,
                geometry_signals=geometry,
                missing_or_inferred_values=[
                    "true_flat_pattern",
                    "bend_deductions",
                    "inside_bend_radii_validation",
                    "grain_direction",
                    "laser_or_punch_process_selection",
                ],
            ),
        )

    def _geometry_signals(self, features: FeatureExtractionResult, material: object) -> dict[str, float]:
        signals = sheet_metal_signals(features)
        raw_thickness_mm = raw_thin_shell_thickness_mm(features)
        snap = _snap_thickness_to_gauge(raw_thickness_mm, material)
        thickness_mm = snap["estimated_thickness_mm"]
        unfold = neutral_axis_unfold_metrics(features, thickness_mm, material.k_factor)
        cut_length_base_mm, cut_length_method = estimated_cut_length_mm(features)
        flat_area_mm2 = unfold["flat_pattern_area_cm2"] * 100.0
        blank_volume_cm3 = flat_area_mm2 * thickness_mm / 1000.0 / self.rate_card.defaults.sheet_utilization
        blank_mass_kg = blank_volume_cm3 * material.density_g_cm3 / 1000.0
        cut_length_mm = cut_length_base_mm * self.rate_card.defaults.flat_pattern_allowance_multiplier
        pierce_count = len(features.holes) + len(features.pockets)
        signals.update(
            {
                "raw_estimated_thickness_mm": raw_thickness_mm,
                "estimated_thickness_mm": thickness_mm,
                "matched_gauge": snap["matched_gauge"],
                "gauge_material_family": material.gauge_material_family,
                "thickness_snap_delta_mm": thickness_mm - raw_thickness_mm,
                "thickness_snap_method": snap["snap_method"],
                **unfold,
                "flat_blank_area_cm2": flat_area_mm2 / 100.0,
                "blank_mass_kg": blank_mass_kg,
                "estimated_cut_length_mm": cut_length_mm,
                "cut_length_estimation_method": cut_length_method,
                "pierce_count": float(pierce_count),
            }
        )
        return signals

    def _material_line_item(self, geometry: dict[str, float], material: object, quantity: int) -> PricingLineItem:
        amount = geometry["blank_mass_kg"] * material.sheet_usd_per_kg * quantity
        return PricingLineItem(
            code="sheet_material",
            label=f"Sheet material: {material.label}",
            amount=_money(amount),
            basis="estimated flat blank, inferred thickness, material density, and sheet utilization",
            details={
                "blank_mass_kg_per_part": geometry["blank_mass_kg"],
                "flat_pattern_area_cm2": geometry["flat_pattern_area_cm2"],
                "estimated_thickness_mm": geometry["estimated_thickness_mm"],
                "matched_gauge": geometry["matched_gauge"],
                "sheet_usd_per_kg": material.sheet_usd_per_kg,
                "sheet_utilization": self.rate_card.defaults.sheet_utilization,
                "quantity": quantity,
            },
        )

    def _setup_line_item(self) -> PricingLineItem:
        amount = self.rate_card.defaults.setup_programming_minutes / 60.0 * self.rate_card.shop_rates.programming_hourly_usd
        return PricingLineItem(
            code="setup_programming",
            label="Setup and programming",
            amount=_money(amount),
            basis="sheet-metal setup/programming allowance",
            details={
                "setup_programming_minutes": self.rate_card.defaults.setup_programming_minutes,
                "programming_hourly_usd": self.rate_card.shop_rates.programming_hourly_usd,
            },
        )

    def _cutting_line_item(self, geometry: dict[str, float], material: object, quantity: int) -> PricingLineItem:
        cut_minutes = geometry["estimated_cut_length_mm"] / self.rate_card.defaults.cutting_speed_mm_min
        pierce_minutes = geometry["pierce_count"] * self.rate_card.defaults.pierce_seconds_each / 60.0
        minutes_per_part = (cut_minutes + pierce_minutes) * material.cutting_multiplier
        amount = minutes_per_part / 60.0 * self.rate_card.shop_rates.cutting_hourly_usd * quantity
        return PricingLineItem(
            code="cutting",
            label="Cutting and pierces",
            amount=_money(amount),
            basis="estimated cut length, pierce count, material cutting multiplier, and cutting hourly rate",
            details={
                "cut_minutes_per_part": cut_minutes,
                "pierce_minutes_per_part": pierce_minutes,
                "cutting_multiplier": material.cutting_multiplier,
                "cutting_hourly_usd": self.rate_card.shop_rates.cutting_hourly_usd,
                "quantity": quantity,
            },
        )

    def _bend_line_item(self, geometry: dict[str, float], quantity: int) -> PricingLineItem:
        bend_minutes = geometry["bend_candidate_count"] * self.rate_card.defaults.bend_minutes_each
        amount = bend_minutes / 60.0 * self.rate_card.shop_rates.brake_hourly_usd * quantity
        return PricingLineItem(
            code="bending",
            label="Bending",
            amount=_money(amount),
            basis="candidate bend count and brake press rate",
            details={
                "bend_candidate_count": int(geometry["bend_candidate_count"]),
                "bend_minutes_each": self.rate_card.defaults.bend_minutes_each,
                "brake_hourly_usd": self.rate_card.shop_rates.brake_hourly_usd,
                "k_factor": geometry["k_factor"],
                "bend_allowance_total_mm": geometry["bend_allowance_total_mm"],
                "bend_deduction_total_mm": geometry["bend_deduction_total_mm"],
                "quantity": quantity,
            },
        )

    def _deburr_qc_line_item(self, quantity: int) -> PricingLineItem:
        minutes = self.rate_card.defaults.deburr_qc_minutes_per_part
        amount = minutes / 60.0 * self.rate_card.shop_rates.deburr_qc_hourly_usd * quantity
        return PricingLineItem(
            code="deburr_qc",
            label="Deburr and basic QC",
            amount=_money(amount),
            basis="per-part sheet-metal deburr and inspection allowance",
            details={
                "minutes_per_part": minutes,
                "deburr_qc_hourly_usd": self.rate_card.shop_rates.deburr_qc_hourly_usd,
                "quantity": quantity,
            },
        )

    def _warnings(self, features: FeatureExtractionResult, geometry: dict[str, float]) -> list[str]:
        warnings = [
            "budgetary_estimate_not_binding",
            "sheet_metal_dfm_not_performed",
            "flat_pattern_estimated_from_neutral_axis_metrics",
        ]
        warnings.extend(features.diagnostics.warnings)
        if geometry["bend_candidate_count"] == 0:
            warnings.append("no_bends_detected_priced_as_flat_sheet_cut_part")
        if geometry["sheet_metal_confidence_score"] < 70:
            warnings.append("sheet_metal_classification_requires_review")
        return warnings

    def _confidence(self, geometry: dict[str, float], warnings: list[str]) -> float:
        confidence = 0.68 if geometry["sheet_metal_confidence_score"] >= 80 else 0.55
        if geometry["bend_candidate_count"] == 0:
            confidence -= 0.05
        if any("requires_review" in warning for warning in warnings):
            confidence -= 0.08
        return round(max(0.25, min(0.78, confidence)), 2)


def _money(value: float) -> float:
    return round(float(value) + 0.0, 2)


def _snap_thickness_to_gauge(raw_thickness_mm: float, material: object) -> dict[str, object]:
    gauges = sorted(material.gauges, key=lambda gauge: gauge.thickness_mm)
    if raw_thickness_mm <= 0 or not gauges:
        return {
            "estimated_thickness_mm": raw_thickness_mm,
            "matched_gauge": None,
            "snap_method": "raw_thin_shell",
        }

    closest = min(gauges, key=lambda gauge: abs(gauge.thickness_mm - raw_thickness_mm))
    closest_relative_delta = abs(closest.thickness_mm - raw_thickness_mm) / max(raw_thickness_mm, 1e-6)
    if closest_relative_delta <= 0.08:
        return {
            "estimated_thickness_mm": closest.thickness_mm,
            "matched_gauge": closest.gauge,
            "snap_method": "nearest_material_gauge",
        }

    thicker_or_equal = [gauge for gauge in gauges if gauge.thickness_mm >= raw_thickness_mm]
    if thicker_or_equal:
        next_thicker = min(thicker_or_equal, key=lambda gauge: gauge.thickness_mm)
        upward_relative_delta = (next_thicker.thickness_mm - raw_thickness_mm) / max(next_thicker.thickness_mm, 1e-6)
        if upward_relative_delta <= 0.25:
            return {
                "estimated_thickness_mm": next_thicker.thickness_mm,
                "matched_gauge": next_thicker.gauge,
                "snap_method": "next_thicker_material_gauge",
            }

    if closest_relative_delta <= 0.25:
        return {
            "estimated_thickness_mm": closest.thickness_mm,
            "matched_gauge": closest.gauge,
            "snap_method": "nearest_material_gauge_wide_tolerance",
        }
    return {
        "estimated_thickness_mm": raw_thickness_mm,
        "matched_gauge": None,
        "snap_method": "raw_thin_shell_outside_gauge_tolerance",
    }
