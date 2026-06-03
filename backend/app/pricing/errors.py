from __future__ import annotations

from typing import Any


class PricingError(Exception):
    code = "pricing_error"

    def __init__(self, message: str, **details: Any) -> None:
        super().__init__(message)
        self.message = message
        self.details = details

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "details": self.details}


class PricingInputError(PricingError):
    code = "pricing_input_invalid"


class RateCardLoadError(PricingError):
    code = "rate_card_load_failed"


class RateCardValidationError(PricingError):
    code = "rate_card_invalid"
