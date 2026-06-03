from pathlib import Path

import pytest

from app.cad.feature_extractor import FeatureExtractor
from app.pricing.sheet_metal import SheetMetalBudgetaryPricer
from app.schemas.pricing import SheetMetalPricingRequest, SheetMetalPricingResult
from test_feature_extraction import _make_box_shape, _write_step


def _request(
    material: str = "aluminum_5052",
    quantity: int = 1,
    finish: str = "raw",
    lead_time: str = "standard",
) -> SheetMetalPricingRequest:
    return SheetMetalPricingRequest(
        material=material,
        quantity=quantity,
        finish=finish,
        lead_time_class=lead_time,
    )


def _features(path: Path):
    return FeatureExtractor().extract_from_path(str(path))


def _line(result: SheetMetalPricingResult, code: str):
    return next(item for item in result.line_items if item.code == code)


def test_thin_panel_produces_sheet_metal_quote(tmp_path: Path) -> None:
    step_path = tmp_path / "thin_panel.step"
    _write_step(step_path, _make_box_shape(160.0, 90.0, 2.0))

    result = SheetMetalBudgetaryPricer().price(_features(step_path), _request())

    assert isinstance(result, SheetMetalPricingResult)
    assert result.process == "sheet_metal"
    assert result.subtotal >= 125.0
    assert result.unit_price == result.subtotal
    assert result.diagnostics.geometry_signals["raw_estimated_thickness_mm"] == pytest.approx(1.93, abs=0.05)
    assert result.diagnostics.geometry_signals["estimated_thickness_mm"] == pytest.approx(2.053, abs=1e-3)
    assert result.diagnostics.geometry_signals["matched_gauge"] == 12
    assert result.diagnostics.geometry_signals["sheet_metal_confidence_score"] >= 70.0
    assert _line(result, "sheet_material").amount > 0
    assert _line(result, "cutting").amount > 0
    assert "flat_pattern_estimated_from_neutral_axis_unfold_metrics" in result.assumptions


def test_apcd_sheet_metal_quote_uses_stainless_gauge_and_eight_bends() -> None:
    step_path = Path(__file__).parent / "fixtures" / "apcd-816.stp"

    result = SheetMetalBudgetaryPricer().price(_features(step_path), _request(material="stainless_304"))
    geometry = result.diagnostics.geometry_signals

    assert geometry["raw_estimated_thickness_mm"] == pytest.approx(2.46, abs=0.05)
    assert geometry["estimated_thickness_mm"] == pytest.approx(2.778, abs=1e-3)
    assert geometry["matched_gauge"] == 12
    assert geometry["gauge_material_family"] == "stainless_steel"
    assert geometry["bend_candidate_count"] == 8
    assert geometry["flat_pattern_area_cm2"] > 0
    assert geometry["k_factor"] == pytest.approx(0.45)
    assert geometry["bend_allowance_total_mm"] > 0
    assert geometry["bend_deduction_total_mm"] >= 0
    assert geometry["flat_pattern_estimation_method"] in {
        "planar_faces_plus_bend_allowance",
        "volume_divided_by_thickness",
    }
    assert _line(result, "bending").details["bend_candidate_count"] == 8
    assert _line(result, "sheet_material").details["flat_pattern_area_cm2"] == pytest.approx(
        geometry["flat_pattern_area_cm2"]
    )


def test_apcd_824_sheet_metal_quote_uses_stainless_gauge_and_four_bends() -> None:
    step_path = Path(__file__).parent / "fixtures" / "apcd-824.stp"

    result = SheetMetalBudgetaryPricer().price(_features(step_path), _request(material="stainless_304"))
    geometry = result.diagnostics.geometry_signals

    assert geometry["raw_estimated_thickness_mm"] == pytest.approx(2.33, abs=0.05)
    assert geometry["estimated_thickness_mm"] == pytest.approx(2.778, abs=1e-3)
    assert geometry["matched_gauge"] == 12
    assert geometry["bend_candidate_count"] == 4
    assert geometry["flat_pattern_area_cm2"] > 0
    assert geometry["k_factor"] == pytest.approx(0.45)
    assert geometry["bend_allowance_total_mm"] > 0
    assert geometry["bend_deduction_total_mm"] >= 0
    assert geometry["cut_length_estimation_method"] in {"boundary_edges", "bounding_box_perimeter"}
    assert _line(result, "bending").details["bend_candidate_count"] == 4


def test_sheet_metal_quantity_tier_reduces_unit_price(tmp_path: Path) -> None:
    step_path = tmp_path / "thin_panel.step"
    _write_step(step_path, _make_box_shape(160.0, 90.0, 2.0))
    features = _features(step_path)
    pricer = SheetMetalBudgetaryPricer()

    single = pricer.price(features, _request(quantity=1))
    many = pricer.price(features, _request(quantity=50))

    assert many.unit_price < single.unit_price
    assert _line(many, "quantity_tier_adjustment").amount < 0


@pytest.mark.parametrize(
    ("material", "expected_family"),
    [
        ("aluminum_5052", "aluminum"),
        ("steel_crs", "cold_rolled_steel"),
        ("stainless_304", "stainless_steel"),
        ("galvanized_steel", "galvanized_steel"),
    ],
)
def test_generated_panel_snaps_against_selected_material_gauge_table(
    tmp_path: Path,
    material: str,
    expected_family: str,
) -> None:
    step_path = tmp_path / "thin_panel.step"
    _write_step(step_path, _make_box_shape(160.0, 90.0, 2.0))

    result = SheetMetalBudgetaryPricer().price(_features(step_path), _request(material=material))
    geometry = result.diagnostics.geometry_signals

    assert geometry["matched_gauge"] is not None
    assert geometry["gauge_material_family"] == expected_family
    assert geometry["estimated_thickness_mm"] > 0
    assert geometry["raw_estimated_thickness_mm"] > 0


def test_sheet_metal_finish_and_lead_time_increase_quote(tmp_path: Path) -> None:
    step_path = tmp_path / "thin_panel.step"
    _write_step(step_path, _make_box_shape(160.0, 90.0, 2.0))
    features = _features(step_path)
    pricer = SheetMetalBudgetaryPricer()

    standard = pricer.price(features, _request(quantity=100))
    coated = pricer.price(features, _request(quantity=100, finish="powder_coat"))
    expedited = pricer.price(features, _request(quantity=100, lead_time="expedited"))

    assert coated.subtotal > standard.subtotal
    assert expedited.subtotal > standard.subtotal
