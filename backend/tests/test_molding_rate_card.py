import pytest

from app.pricing.errors import PricingInputError
from app.pricing.molding_rate_card import get_default_molding_rate_card


def test_molding_rate_card_loads_required_tables() -> None:
    rate_card = get_default_molding_rate_card()

    assert rate_card.process == "injection_molding"
    assert rate_card.currency == "USD"
    assert {"abs", "pp", "pc", "nylon_66", "acetal_pom"} <= set(rate_card.materials)
    assert {"prototype", "bridge", "production", "high_volume"} <= set(rate_card.mold_classes)
    assert rate_card.material("abs").label == "ABS"
    assert rate_card.mold_class("production").base_tooling_usd > 0


def test_molding_rate_card_rejects_unsupported_material_and_class() -> None:
    rate_card = get_default_molding_rate_card()

    with pytest.raises(PricingInputError):
        rate_card.material("pla")

    with pytest.raises(PricingInputError):
        rate_card.mold_class("garage_tool")
