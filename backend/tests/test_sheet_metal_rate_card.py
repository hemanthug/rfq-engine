import pytest

from app.pricing.errors import PricingInputError
from app.pricing.sheet_metal_rate_card import get_default_sheet_metal_rate_card


def test_sheet_metal_rate_card_loads_required_tables() -> None:
    rate_card = get_default_sheet_metal_rate_card()

    assert rate_card.process == "sheet_metal"
    assert rate_card.currency == "USD"
    assert {"aluminum_5052", "steel_crs", "stainless_304", "galvanized_steel"} <= set(rate_card.materials)
    assert {"raw", "powder_coat", "grained"} <= set(rate_card.finishes)
    assert rate_card.material("aluminum_5052").density_g_cm3 > 0
    assert rate_card.material("stainless_304").gauge_material_family == "stainless_steel"
    assert rate_card.material("stainless_304").k_factor == pytest.approx(0.45)
    assert any(
        gauge.gauge == 12 and gauge.thickness_mm == pytest.approx(2.778)
        for gauge in rate_card.material("stainless_304").gauges
    )


def test_sheet_metal_rate_card_rejects_unknown_inputs() -> None:
    rate_card = get_default_sheet_metal_rate_card()

    with pytest.raises(PricingInputError):
        rate_card.material("cardboard")

    with pytest.raises(PricingInputError):
        rate_card.finish("mirror")
