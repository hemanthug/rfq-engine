from pathlib import Path

from app.cad.feature_extractor import FeatureExtractor
from app.pricing.cnc import CncBudgetaryPricer
from app.schemas.pricing import CncPricingRequest, CncPricingResult
from test_feature_extraction import (
    _make_box_shape,
    _write_blind_hole_block_step,
    _write_rectangular_pocket_block_step,
    _write_step,
    _write_through_hole_plate_step,
)


def _request(
    material: str = "aluminum_6061",
    quantity: int = 1,
    tolerance: str = "standard",
    finish: str = "as_machined",
    lead_time: str = "standard",
) -> CncPricingRequest:
    return CncPricingRequest(
        material=material,
        quantity=quantity,
        tolerance_class=tolerance,
        finish=finish,
        lead_time_class=lead_time,
    )


def _features(path: Path):
    return FeatureExtractor().extract_from_path(str(path))


def _line(result: CncPricingResult, code: str):
    return next(item for item in result.line_items if item.code == code)


def test_generated_box_produces_budgetary_cnc_line_items(tmp_path: Path) -> None:
    step_path = tmp_path / "large_box.step"
    _write_step(step_path, _make_box_shape(80.0, 60.0, 40.0))

    result = CncBudgetaryPricer().price(_features(step_path), _request())

    assert isinstance(result, CncPricingResult)
    assert result.process == "cnc_3_axis_milling"
    assert result.currency == "USD"
    assert result.subtotal >= 125.0
    assert result.unit_price == result.subtotal
    assert result.confidence > 0
    assert result.model_dump_json()
    codes = {item.code for item in result.line_items}
    assert {
        "material",
        "setup_programming",
        "machine_time",
        "deburr_qc",
        "minimum_order_adjustment",
    } <= codes
    assert "budgetary_estimate_not_binding" in result.assumptions
    assert "toolpaths_not_generated" in result.diagnostics.missing_or_inferred_values
    machine_time = _line(result, "machine_time")
    assert machine_time.details["profile_complexity_candidate_count"] == 0
    assert machine_time.details["profile_complexity_multiplier"] == 1.0


def test_through_hole_fixture_adds_feature_operation_cost(tmp_path: Path) -> None:
    step_path = tmp_path / "through_hole.step"
    _write_through_hole_plate_step(step_path)

    result = CncBudgetaryPricer().price(_features(step_path), _request())

    feature_ops = _line(result, "feature_operations")
    assert feature_ops.amount > 0
    assert feature_ops.details["through_holes"] == 1


def test_blind_hole_fixture_adds_feature_operation_cost(tmp_path: Path) -> None:
    step_path = tmp_path / "blind_hole.step"
    _write_blind_hole_block_step(step_path)

    result = CncBudgetaryPricer().price(_features(step_path), _request())

    feature_ops = _line(result, "feature_operations")
    assert feature_ops.amount > 0
    assert feature_ops.details["blind_holes"] == 1


def test_pocket_fixture_adds_feature_operation_cost(tmp_path: Path) -> None:
    step_path = tmp_path / "pocket.step"
    _write_rectangular_pocket_block_step(step_path)

    result = CncBudgetaryPricer().price(_features(step_path), _request())

    feature_ops = _line(result, "feature_operations")
    assert feature_ops.amount > 0
    assert feature_ops.details["pockets"] >= 1


def test_pulley_profile_complexity_increases_machine_time_without_pricing_teeth_as_holes() -> None:
    step_path = Path(__file__).parent / "fixtures" / "HTD5M-20W-48Z-D20.STEP"

    result = CncBudgetaryPricer().price(_features(step_path), _request())

    machine_time = _line(result, "machine_time")
    feature_ops = _line(result, "feature_operations")
    assert feature_ops.label == "Feature operations"
    assert feature_ops.details["through_holes"] == 3
    assert feature_ops.amount == 12.0
    assert machine_time.details["profile_complexity_candidate_count"] == 145
    assert machine_time.details["profile_complexity_multiplier"] > 1.0
    assert machine_time.amount > 15.62
    assert result.subtotal > 146.62


def test_shaft_profile_complexity_increases_machine_time_without_pricing_teeth_as_holes() -> None:
    step_path = Path(__file__).parent / "fixtures" / "flx-4589.stp"

    result = CncBudgetaryPricer().price(_features(step_path), _request())

    machine_time = _line(result, "machine_time")
    feature_ops = _line(result, "feature_operations")
    assert feature_ops.label == "Feature operations"
    assert feature_ops.details["through_holes"] == 0
    assert feature_ops.amount == 0.0
    assert machine_time.details["profile_complexity_candidate_count"] == 12
    assert machine_time.details["profile_complexity_multiplier"] > 1.0


def test_quantity_tiers_reduce_effective_unit_price(tmp_path: Path) -> None:
    step_path = tmp_path / "box.step"
    _write_step(step_path, _make_box_shape(80.0, 60.0, 40.0))
    features = _features(step_path)
    pricer = CncBudgetaryPricer()

    single = pricer.price(features, _request(quantity=1))
    ten = pricer.price(features, _request(quantity=10))

    assert ten.unit_price < single.unit_price
    assert _line(ten, "quantity_tier_adjustment").amount < 0


def test_tolerance_and_lead_time_increase_quote(tmp_path: Path) -> None:
    step_path = tmp_path / "box.step"
    _write_step(step_path, _make_box_shape(120.0, 90.0, 50.0))
    features = _features(step_path)
    pricer = CncBudgetaryPricer()

    standard = pricer.price(features, _request())
    tight = pricer.price(features, _request(tolerance="tight"))
    expedited = pricer.price(features, _request(lead_time="expedited"))

    assert _line(tight, "machine_time").amount > _line(standard, "machine_time").amount
    assert expedited.subtotal > standard.subtotal
    assert _line(expedited, "lead_time_adjustment").amount > 0


def test_stainless_costs_more_machine_time_than_aluminum(tmp_path: Path) -> None:
    step_path = tmp_path / "box.step"
    _write_step(step_path, _make_box_shape(120.0, 90.0, 50.0))
    features = _features(step_path)
    pricer = CncBudgetaryPricer()

    aluminum = pricer.price(features, _request(material="aluminum_6061"))
    stainless = pricer.price(features, _request(material="stainless_304"))

    assert _line(stainless, "machine_time").amount > _line(aluminum, "machine_time").amount
