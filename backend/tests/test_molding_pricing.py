from pathlib import Path

from app.cad.feature_extractor import FeatureExtractor
from app.pricing.molding import MoldingBudgetaryPricer
from app.schemas.pricing import MoldingPricingRequest, MoldingPricingResult
from test_feature_extraction import _make_box_shape, _write_step


def _request(
    material: str = "abs",
    quantity: int = 1000,
    annual_volume: int = 10000,
    cavities: int = 1,
    mold_class: str = "production",
    finish: str = "standard_spi_b3",
    lead_time: str = "standard",
) -> MoldingPricingRequest:
    return MoldingPricingRequest(
        material=material,
        quantity=quantity,
        annual_volume=annual_volume,
        cavities=cavities,
        mold_class=mold_class,
        finish=finish,
        lead_time_class=lead_time,
    )


def _features(path: Path):
    return FeatureExtractor().extract_from_path(str(path))


def _line(result: MoldingPricingResult, code: str):
    return next(
        item for item in [*result.tooling_line_items, *result.production_line_items] if item.code == code
    )


def test_generated_box_produces_molding_tooling_and_production_quote(tmp_path: Path) -> None:
    step_path = tmp_path / "box.step"
    _write_step(step_path, _make_box_shape(60.0, 40.0, 25.0))

    result = MoldingBudgetaryPricer().price(_features(step_path), _request())

    assert isinstance(result, MoldingPricingResult)
    assert result.process == "injection_molding"
    assert result.tooling_cost > 0
    assert result.production_subtotal > 0
    assert result.total_first_order_cost == result.tooling_cost + result.production_subtotal
    assert result.unit_price == round(result.production_subtotal / result.quantity, 2)
    assert result.diagnostics.effective_amortized_unit_price == round(
        result.total_first_order_cost / result.quantity,
        2,
    )
    assert "dfm_not_performed" in result.warnings
    assert "moldflow_not_performed" in result.warnings
    assert _line(result, "press_time").amount > 0


def test_auto_cavity_recommendation_returns_one_for_prototype_low_volume(tmp_path: Path) -> None:
    step_path = tmp_path / "box.step"
    _write_step(step_path, _make_box_shape(40.0, 30.0, 20.0))

    result = MoldingBudgetaryPricer().price(
        _features(step_path),
        _request(quantity=100, annual_volume=1000, cavities=None, mold_class="prototype"),
    )

    cavity = result.diagnostics.cavity_recommendation
    assert result.request.cavities == 1
    assert cavity.recommended_cavities == 1
    assert cavity.user_overrode_cavities is False
    assert any(
        candidate.cavities == 2 and "exceeds_mold_class_cavity_cap" in candidate.rejection_reasons
        for candidate in cavity.candidate_cavity_results
    )


def test_auto_cavity_recommendation_can_select_multi_cavity_for_high_volume(tmp_path: Path) -> None:
    step_path = tmp_path / "small_box.step"
    _write_step(step_path, _make_box_shape(20.0, 15.0, 8.0))

    result = MoldingBudgetaryPricer().price(
        _features(step_path),
        _request(quantity=10000, annual_volume=200000, cavities=None, mold_class="high_volume"),
    )

    cavity = result.diagnostics.cavity_recommendation
    assert result.request.cavities in {2, 4, 8}
    assert cavity.recommended_cavities == result.request.cavities
    assert cavity.user_overrode_cavities is False
    assert any(candidate.cavities == 8 and candidate.feasible for candidate in cavity.candidate_cavity_results)


def test_explicit_cavity_override_is_respected(tmp_path: Path) -> None:
    step_path = tmp_path / "box.step"
    _write_step(step_path, _make_box_shape(40.0, 30.0, 20.0))

    result = MoldingBudgetaryPricer().price(
        _features(step_path),
        _request(quantity=1000, annual_volume=50000, cavities=4, mold_class="production"),
    )

    cavity = result.diagnostics.cavity_recommendation
    assert result.request.cavities == 4
    assert cavity.recommended_cavities == 4
    assert cavity.user_overrode_cavities is True


def test_quantity_and_annual_volume_affect_molding_unit_price(tmp_path: Path) -> None:
    step_path = tmp_path / "box.step"
    _write_step(step_path, _make_box_shape(60.0, 40.0, 25.0))
    features = _features(step_path)
    pricer = MoldingBudgetaryPricer()

    low_volume = pricer.price(features, _request(quantity=500, annual_volume=5000))
    high_volume = pricer.price(features, _request(quantity=5000, annual_volume=100000))

    assert high_volume.unit_price < low_volume.unit_price
    assert _line(low_volume, "press_time").details["annual_volume_multiplier"] > _line(
        high_volume,
        "press_time",
    ).details["annual_volume_multiplier"]


def test_mold_class_changes_tooling_cost(tmp_path: Path) -> None:
    step_path = tmp_path / "box.step"
    _write_step(step_path, _make_box_shape(60.0, 40.0, 25.0))
    features = _features(step_path)
    pricer = MoldingBudgetaryPricer()

    prototype = pricer.price(features, _request(mold_class="prototype"))
    production = pricer.price(features, _request(mold_class="production"))

    assert production.tooling_cost > prototype.tooling_cost
    assert "prototype_tooling_limited_life" in prototype.warnings


def test_pulley_profile_complexity_affects_molding_tooling_and_cycle_time() -> None:
    step_path = Path(__file__).parent / "fixtures" / "HTD5M-20W-48Z-D20.STEP"

    result = MoldingBudgetaryPricer().price(_features(step_path), _request(quantity=1000, annual_volume=20000))

    press_time = _line(result, "press_time")
    geometry_complexity = _line(result, "geometry_complexity_adjustment")
    assert result.diagnostics.geometry_signals["profile_complexity_candidate_count"] == 145.0
    assert press_time.details["profile_complexity_candidate_count"] == 145
    assert press_time.details["profile_complexity_multiplier"] > 1.0
    assert geometry_complexity.amount > 0
    assert "profile_geometry_priced_as_molding_complexity" in result.warnings


def test_simple_box_has_no_profile_complexity_multiplier(tmp_path: Path) -> None:
    step_path = tmp_path / "box.step"
    _write_step(step_path, _make_box_shape(40.0, 30.0, 20.0))

    result = MoldingBudgetaryPricer().price(_features(step_path), _request())

    assert result.diagnostics.geometry_signals["profile_complexity_candidate_count"] == 0.0
    assert result.diagnostics.geometry_signals["profile_complexity_multiplier"] == 1.0
