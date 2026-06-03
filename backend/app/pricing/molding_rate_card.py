from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, ValidationError, model_validator

from app.pricing.errors import PricingInputError, RateCardLoadError, RateCardValidationError


DEFAULT_MOLDING_RATE_CARD_PATH = Path(__file__).resolve().parent / "rate_cards" / "injection_molding_v1.yaml"


class MoldingShopRates(BaseModel):
    press_hourly_usd: float = Field(gt=0)
    setup_hourly_usd: float = Field(gt=0)
    handling_qc_hourly_usd: float = Field(gt=0)
    minimum_production_order_usd: float = Field(ge=0)


class MoldingDefaults(BaseModel):
    base_cycle_seconds: float = Field(gt=0)
    cooling_seconds_per_mm_wall_proxy: float = Field(ge=0)
    handling_seconds_per_part: float = Field(ge=0)
    setup_changeover_hours: float = Field(ge=0)
    scrap_factor: float = Field(gt=0)
    tool_complexity_multiplier_at_100: float = Field(gt=0)
    cycle_complexity_multiplier_at_100: float = Field(gt=0)


class MoldingMaterialRate(BaseModel):
    label: str
    density_g_cm3: float = Field(gt=0)
    resin_usd_per_kg: float = Field(ge=0)
    processing_multiplier: float = Field(gt=0)


class MoldingClassRate(BaseModel):
    label: str
    base_tooling_usd: float = Field(ge=0)
    tooling_multiplier: float = Field(gt=0)
    max_shots: int | None = Field(default=None, gt=0)
    warnings: list[str] = Field(default_factory=list)


class MoldingFinishRate(BaseModel):
    label: str
    tooling_add_usd: float = Field(ge=0)
    production_multiplier: float = Field(gt=0)
    warnings: list[str] = Field(default_factory=list)


class MoldingLeadTimeRate(BaseModel):
    label: str
    multiplier: float = Field(gt=0)
    warnings: list[str] = Field(default_factory=list)


class MoldingAnnualVolumeTier(BaseModel):
    min_annual_volume: int = Field(gt=0)
    max_annual_volume: int | None = Field(default=None, gt=0)
    production_multiplier: float = Field(gt=0)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_range(self) -> "MoldingAnnualVolumeTier":
        if self.max_annual_volume is not None and self.max_annual_volume < self.min_annual_volume:
            raise ValueError("max_annual_volume must be greater than or equal to min_annual_volume")
        return self


class MoldingRateCard(BaseModel):
    version: str
    kind: str
    process: str
    currency: str
    shop_rates: MoldingShopRates
    defaults: MoldingDefaults
    materials: dict[str, MoldingMaterialRate]
    mold_classes: dict[str, MoldingClassRate]
    finishes: dict[str, MoldingFinishRate]
    lead_time_classes: dict[str, MoldingLeadTimeRate]
    annual_volume_tiers: list[MoldingAnnualVolumeTier]

    @model_validator(mode="after")
    def validate_required_tables(self) -> "MoldingRateCard":
        if not self.materials:
            raise ValueError("materials must not be empty")
        if not self.mold_classes:
            raise ValueError("mold_classes must not be empty")
        if not self.finishes:
            raise ValueError("finishes must not be empty")
        if not self.lead_time_classes:
            raise ValueError("lead_time_classes must not be empty")
        if not self.annual_volume_tiers:
            raise ValueError("annual_volume_tiers must not be empty")
        return self

    def material(self, material_id: str) -> MoldingMaterialRate:
        return _lookup(self.materials, "material", material_id)

    def mold_class(self, mold_class_id: str) -> MoldingClassRate:
        return _lookup(self.mold_classes, "mold_class", mold_class_id)

    def finish(self, finish_id: str) -> MoldingFinishRate:
        return _lookup(self.finishes, "finish", finish_id)

    def lead_time(self, lead_time_id: str) -> MoldingLeadTimeRate:
        return _lookup(self.lead_time_classes, "lead_time_class", lead_time_id)

    def annual_volume_tier(self, annual_volume: int) -> MoldingAnnualVolumeTier:
        for tier in self.annual_volume_tiers:
            if annual_volume >= tier.min_annual_volume and (
                tier.max_annual_volume is None or annual_volume <= tier.max_annual_volume
            ):
                return tier
        raise PricingInputError("No annual-volume tier matches the requested volume.", annual_volume=annual_volume)


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


def load_molding_rate_card(path: str | Path = DEFAULT_MOLDING_RATE_CARD_PATH) -> MoldingRateCard:
    rate_card_path = Path(path)
    try:
        raw = yaml.safe_load(rate_card_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RateCardLoadError("Unable to read injection molding rate card.", path=str(rate_card_path)) from exc
    except yaml.YAMLError as exc:
        raise RateCardLoadError("Unable to parse injection molding rate card YAML.", path=str(rate_card_path)) from exc

    try:
        return MoldingRateCard.model_validate(raw)
    except ValidationError as exc:
        raise RateCardValidationError(
            "Injection molding rate card failed validation.",
            path=str(rate_card_path),
            errors=exc.errors(),
        ) from exc


@lru_cache
def get_default_molding_rate_card() -> MoldingRateCard:
    return load_molding_rate_card()
