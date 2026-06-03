from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, ValidationError, model_validator

from app.pricing.errors import PricingInputError, RateCardLoadError, RateCardValidationError


DEFAULT_RATE_CARD_PATH = Path(__file__).resolve().parent / "rate_cards" / "cnc_3_axis_v1.yaml"


class ShopRates(BaseModel):
    machine_hourly_usd: float = Field(gt=0)
    setup_hourly_usd: float = Field(gt=0)
    deburr_qc_hourly_usd: float = Field(gt=0)
    minimum_order_usd: float = Field(ge=0)


class PricingDefaults(BaseModel):
    stock_allowance_mm_per_side: float = Field(ge=0)
    scrap_factor: float = Field(gt=0)
    pre_cam_overhead_multiplier: float = Field(gt=0)
    base_setup_programming_minutes: float = Field(ge=0)
    complexity_setup_minutes_at_100: float = Field(ge=0)
    base_deburr_qc_minutes_per_part: float = Field(ge=0)
    finishing_minutes_per_100_cm2: float = Field(ge=0)
    tooling_usd_per_part: float = Field(ge=0)


class MaterialRate(BaseModel):
    label: str
    density_g_cm3: float = Field(gt=0)
    material_usd_per_kg: float = Field(ge=0)
    machinability_multiplier: float = Field(gt=0)
    material_removal_rate_cm3_min: float = Field(gt=0)


class MultiplierRate(BaseModel):
    label: str
    multiplier: float = Field(gt=0)
    warnings: list[str] = Field(default_factory=list)


class FinishRate(MultiplierRate):
    per_part_add_usd: float = Field(ge=0)


class QuantityTier(BaseModel):
    min_quantity: int = Field(gt=0)
    max_quantity: int | None = Field(default=None, gt=0)
    multiplier: float = Field(gt=0)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_range(self) -> "QuantityTier":
        if self.max_quantity is not None and self.max_quantity < self.min_quantity:
            raise ValueError("max_quantity must be greater than or equal to min_quantity")
        return self


class FeatureOperationRates(BaseModel):
    through_hole_usd_each: float = Field(ge=0)
    blind_hole_usd_each: float = Field(ge=0)
    pocket_usd_each: float = Field(ge=0)


class CncRateCard(BaseModel):
    version: str
    kind: str
    process: str
    currency: str
    shop_rates: ShopRates
    defaults: PricingDefaults
    materials: dict[str, MaterialRate]
    tolerance_classes: dict[str, MultiplierRate]
    finishes: dict[str, FinishRate]
    lead_time_classes: dict[str, MultiplierRate]
    quantity_tiers: list[QuantityTier]
    feature_operations: FeatureOperationRates

    @model_validator(mode="after")
    def validate_required_tables(self) -> "CncRateCard":
        required_tables = {
            "materials": self.materials,
            "tolerance_classes": self.tolerance_classes,
            "finishes": self.finishes,
            "lead_time_classes": self.lead_time_classes,
        }
        for table_name, table in required_tables.items():
            if not table:
                raise ValueError(f"{table_name} must not be empty")
        if not self.quantity_tiers:
            raise ValueError("quantity_tiers must not be empty")
        return self

    def material(self, material_id: str) -> MaterialRate:
        return _lookup(self.materials, "material", material_id)

    def tolerance(self, tolerance_id: str) -> MultiplierRate:
        return _lookup(self.tolerance_classes, "tolerance_class", tolerance_id)

    def finish(self, finish_id: str) -> FinishRate:
        return _lookup(self.finishes, "finish", finish_id)

    def lead_time(self, lead_time_id: str) -> MultiplierRate:
        return _lookup(self.lead_time_classes, "lead_time_class", lead_time_id)

    def quantity_tier(self, quantity: int) -> QuantityTier:
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


def load_rate_card(path: str | Path = DEFAULT_RATE_CARD_PATH) -> CncRateCard:
    rate_card_path = Path(path)
    try:
        raw = yaml.safe_load(rate_card_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RateCardLoadError("Unable to read CNC rate card.", path=str(rate_card_path)) from exc
    except yaml.YAMLError as exc:
        raise RateCardLoadError("Unable to parse CNC rate card YAML.", path=str(rate_card_path)) from exc

    try:
        return CncRateCard.model_validate(raw)
    except ValidationError as exc:
        raise RateCardValidationError(
            "CNC rate card failed validation.",
            path=str(rate_card_path),
            errors=exc.errors(),
        ) from exc


@lru_cache
def get_default_rate_card() -> CncRateCard:
    return load_rate_card()
