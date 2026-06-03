from pathlib import Path

import pytest

from app.pricing.errors import PricingInputError, RateCardValidationError
from app.pricing.rate_card import load_rate_card


def test_default_cnc_rate_card_loads_required_tables() -> None:
    rate_card = load_rate_card()

    assert rate_card.version == "cnc_3_axis_v1"
    assert rate_card.kind == "budgetary_defaults"
    assert rate_card.process == "cnc_3_axis_milling"
    assert rate_card.currency == "USD"
    assert set(rate_card.materials) == {
        "aluminum_6061",
        "steel_1018",
        "stainless_304",
        "brass_c360",
        "delrin",
    }
    assert {"standard", "tight", "precision"} <= set(rate_card.tolerance_classes)
    assert {"as_machined", "bead_blasted", "anodized_clear"} <= set(rate_card.finishes)
    assert {"economy", "standard", "expedited"} <= set(rate_card.lead_time_classes)
    assert rate_card.quantity_tier(1).multiplier == 1.0
    assert rate_card.quantity_tier(10).multiplier == 0.9
    assert rate_card.quantity_tier(100).multiplier == 0.75


def test_rate_card_rejects_unknown_inputs() -> None:
    rate_card = load_rate_card()

    with pytest.raises(PricingInputError):
        rate_card.material("titanium")
    with pytest.raises(PricingInputError):
        rate_card.finish("mirror_polished")
    with pytest.raises(PricingInputError):
        rate_card.tolerance("unrealistic")
    with pytest.raises(PricingInputError):
        rate_card.lead_time("tonight")


def test_malformed_rate_card_fails_validation(tmp_path: Path) -> None:
    malformed = tmp_path / "bad_rate_card.yaml"
    malformed.write_text("version: bad\nmaterials: {}\n", encoding="utf-8")

    with pytest.raises(RateCardValidationError) as exc_info:
        load_rate_card(malformed)

    assert exc_info.value.as_dict()["code"] == "rate_card_invalid"
