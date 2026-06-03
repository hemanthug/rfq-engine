from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, ValidationError, model_validator

from app.pricing.errors import PricingInputError, RateCardLoadError, RateCardValidationError


DEFAULT_SHEET_METAL_RATE_CARD_PATH = Path(__file__).resolve().parent / "rate_cards" / "sheet_metal_v1.yaml"


class SheetMetalShopRates(BaseModel):
    programming_hourly_usd: float = Field(gt=0)
    cutting_hourly_usd: float = Field(gt=0)
    brake_hourly_usd: float = Field(gt=0)
    deburr_qc_hourly_usd: float = Field(gt=0)
    minimum_order_usd: float = Field(ge=0)


class SheetMetalDefaults(BaseModel):
    sheet_utilization: float = Field(gt=0, le=1)
    setup_programming_minutes: float = Field(ge=0)
    cutting_speed_mm_min: float = Field(gt=0)
    pierce_seconds_each: float = Field(ge=0)
    bend_minutes_each: float = Field(ge=0)
    deburr_qc_minutes_per_part: float = Field(ge=0)
    flat_pattern_allowance_multiplier: float = Field(gt=0)


class SheetMetalMaterialRate(BaseModel):
    label: str
    density_g_cm3: float = Field(gt=0)
    sheet_usd_per_kg: float = Field(ge=0)
    cutting_multiplier: float = Field(gt=0)
    gauge_material_family: str
    k_factor: float = Field(gt=0, lt=1)
    gauges: list["SheetMetalGaugeThickness"]


class SheetMetalGaugeThickness(BaseModel):
    gauge: int = Field(gt=0)
    thickness_mm: float = Field(gt=0)


class SheetMetalFinishRate(BaseModel):
    label: str
    multiplier: float = Field(gt=0)
    per_part_add_usd: float = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)


class SheetMetalLeadTimeRate(BaseModel):
    label: str
    multiplier: float = Field(gt=0)
    warnings: list[str] = Field(default_factory=list)


class SheetMetalQuantityTier(BaseModel):
    min_quantity: int = Field(gt=0)
    max_quantity: int | None = Field(default=None, gt=0)
    multiplier: float = Field(gt=0)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_range(self) -> "SheetMetalQuantityTier":
        if self.max_quantity is not None and self.max_quantity < self.min_quantity:
            raise ValueError("max_quantity must be greater than or equal to min_quantity")
        return self


class SheetMetalRateCard(BaseModel):
    version: str
    kind: str
    process: str
    currency: str
    shop_rates: SheetMetalShopRates
    defaults: SheetMetalDefaults
    materials: dict[str, SheetMetalMaterialRate]
    finishes: dict[str, SheetMetalFinishRate]
    lead_time_classes: dict[str, SheetMetalLeadTimeRate]
    quantity_tiers: list[SheetMetalQuantityTier]

    @model_validator(mode="after")
    def validate_required_tables(self) -> "SheetMetalRateCard":
        if not self.materials:
            raise ValueError("materials must not be empty")
        if not self.finishes:
            raise ValueError("finishes must not be empty")
        if not self.lead_time_classes:
            raise ValueError("lead_time_classes must not be empty")
        if not self.quantity_tiers:
            raise ValueError("quantity_tiers must not be empty")
        return self

    def material(self, material_id: str) -> SheetMetalMaterialRate:
        return _lookup(self.materials, "material", material_id)

    def finish(self, finish_id: str) -> SheetMetalFinishRate:
        return _lookup(self.finishes, "finish", finish_id)

    def lead_time(self, lead_time_id: str) -> SheetMetalLeadTimeRate:
        return _lookup(self.lead_time_classes, "lead_time_class", lead_time_id)

    def quantity_tier(self, quantity: int) -> SheetMetalQuantityTier:
        for tier in self.quantity_tiers:
            if quantity >= tier.min_quantity and (tier.max_quantity is None or quantity <= tier.max_quantity):
                return tier
        raise PricingInputError("No quantity tier matches the requested quantity.", quantity=quantity)


def _lookup(table: dict[str, object], field_name: str, value: str):
    try:
        return table[value]
    except KeyError as exc:
        raise PricingInputError(
            f"Unsupported {field_name}.",
            field=field_name,
            value=value,
            supported_values=sorted(table.keys()),
        ) from exc


def load_sheet_metal_rate_card(path: str | Path = DEFAULT_SHEET_METAL_RATE_CARD_PATH) -> SheetMetalRateCard:
    rate_card_path = Path(path)
    try:
        raw = yaml.safe_load(rate_card_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RateCardLoadError("Unable to read sheet metal rate card.", path=str(rate_card_path)) from exc
    except yaml.YAMLError as exc:
        raise RateCardLoadError("Unable to parse sheet metal rate card YAML.", path=str(rate_card_path)) from exc

    try:
        return SheetMetalRateCard.model_validate(raw)
    except ValidationError as exc:
        raise RateCardValidationError(
            "Sheet metal rate card failed validation.",
            path=str(rate_card_path),
            errors=exc.errors(),
        ) from exc


@lru_cache
def get_default_sheet_metal_rate_card() -> SheetMetalRateCard:
    return load_sheet_metal_rate_card()
