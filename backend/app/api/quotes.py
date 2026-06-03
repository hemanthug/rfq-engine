from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from pydantic import ValidationError

from app.cad.errors import CadParseError, PreviewMeshTooLargeError
from app.config import Settings
from app.pricing.errors import PricingError, PricingInputError
from app.schemas.pricing import CncPricingRequest, MoldingPricingRequest, SheetMetalPricingRequest
from app.schemas.quote import ApiErrorResponse, MoldingQuoteWorkflowResult, QuoteWorkflowResult, SheetMetalQuoteWorkflowResult
from app.services.errors import UploadFileTooLargeError, UploadValidationError
from app.services.quote_workflow import QuoteWorkflowService


router = APIRouter()


@router.post(
    "/cnc",
    response_model=QuoteWorkflowResult,
    responses={
        400: {"model": ApiErrorResponse},
        413: {"model": ApiErrorResponse},
        422: {"model": ApiErrorResponse},
    },
)
async def create_cnc_quote(
    request: Request,
    file: UploadFile = File(...),
    material: str = Form("aluminum_6061"),
    quantity: int = Form(1),
    tolerance_class: str = Form("standard"),
    finish: str = Form("as_machined"),
    lead_time_class: str = Form("standard"),
    notes: str | None = Form(None),
) -> QuoteWorkflowResult:
    try:
        pricing_request = CncPricingRequest(
            material=material,
            quantity=quantity,
            tolerance_class=tolerance_class,
            finish=finish,
            lead_time_class=lead_time_class,
            notes=notes,
        )
    except ValidationError as exc:
        error = PricingInputError("Pricing form input failed validation.", errors=_serializable_validation_errors(exc))
        raise _http_error(400, error.as_dict()) from exc
    settings: Settings = request.app.state.settings
    service = QuoteWorkflowService(settings)

    try:
        return await service.quote_cnc(file, pricing_request)
    except UploadFileTooLargeError as exc:
        raise _http_error(413, exc.as_dict()) from exc
    except UploadValidationError as exc:
        raise _http_error(400, exc.as_dict()) from exc
    except PreviewMeshTooLargeError as exc:
        raise _http_error(422, exc.as_dict()) from exc
    except CadParseError as exc:
        raise _http_error(422, exc.as_dict()) from exc
    except PricingError as exc:
        raise _http_error(400, exc.as_dict()) from exc


@router.post(
    "/injection-molding",
    response_model=MoldingQuoteWorkflowResult,
    responses={
        400: {"model": ApiErrorResponse},
        413: {"model": ApiErrorResponse},
        422: {"model": ApiErrorResponse},
    },
)
async def create_injection_molding_quote(
    request: Request,
    file: UploadFile = File(...),
    material: str = Form("abs"),
    quantity: int = Form(1000),
    annual_volume: int = Form(10000),
    cavities: str = Form("auto"),
    mold_class: str = Form("production"),
    finish: str = Form("standard_spi_b3"),
    lead_time_class: str = Form("standard"),
    notes: str | None = Form(None),
) -> MoldingQuoteWorkflowResult:
    try:
        parsed_cavities = _parse_molding_cavities(cavities)
        pricing_request = MoldingPricingRequest(
            material=material,
            quantity=quantity,
            annual_volume=annual_volume,
            cavities=parsed_cavities,
            mold_class=mold_class,
            finish=finish,
            lead_time_class=lead_time_class,
            notes=notes,
        )
    except ValidationError as exc:
        error = PricingInputError("Pricing form input failed validation.", errors=_serializable_validation_errors(exc))
        raise _http_error(400, error.as_dict()) from exc
    settings: Settings = request.app.state.settings
    service = QuoteWorkflowService(settings)

    try:
        return await service.quote_injection_molding(file, pricing_request)
    except UploadFileTooLargeError as exc:
        raise _http_error(413, exc.as_dict()) from exc
    except UploadValidationError as exc:
        raise _http_error(400, exc.as_dict()) from exc
    except PreviewMeshTooLargeError as exc:
        raise _http_error(422, exc.as_dict()) from exc
    except CadParseError as exc:
        raise _http_error(422, exc.as_dict()) from exc
    except PricingError as exc:
        raise _http_error(400, exc.as_dict()) from exc


@router.post(
    "/sheet-metal",
    response_model=SheetMetalQuoteWorkflowResult,
    responses={
        400: {"model": ApiErrorResponse},
        413: {"model": ApiErrorResponse},
        422: {"model": ApiErrorResponse},
    },
)
async def create_sheet_metal_quote(
    request: Request,
    file: UploadFile = File(...),
    material: str = Form("aluminum_5052"),
    quantity: int = Form(1),
    finish: str = Form("raw"),
    lead_time_class: str = Form("standard"),
    notes: str | None = Form(None),
) -> SheetMetalQuoteWorkflowResult:
    try:
        pricing_request = SheetMetalPricingRequest(
            material=material,
            quantity=quantity,
            finish=finish,
            lead_time_class=lead_time_class,
            notes=notes,
        )
    except ValidationError as exc:
        error = PricingInputError("Pricing form input failed validation.", errors=_serializable_validation_errors(exc))
        raise _http_error(400, error.as_dict()) from exc
    settings: Settings = request.app.state.settings
    service = QuoteWorkflowService(settings)

    try:
        return await service.quote_sheet_metal(file, pricing_request)
    except UploadFileTooLargeError as exc:
        raise _http_error(413, exc.as_dict()) from exc
    except UploadValidationError as exc:
        raise _http_error(400, exc.as_dict()) from exc
    except PreviewMeshTooLargeError as exc:
        raise _http_error(422, exc.as_dict()) from exc
    except CadParseError as exc:
        raise _http_error(422, exc.as_dict()) from exc
    except PricingError as exc:
        raise _http_error(400, exc.as_dict()) from exc


def _http_error(status_code: int, error: dict) -> HTTPException:
    return HTTPException(status_code=status_code, detail=error)


def _parse_molding_cavities(value: str) -> int | None:
    normalized = value.strip().lower()
    if normalized == "auto":
        return None
    try:
        parsed = int(normalized)
    except ValueError as exc:
        raise ValidationError.from_exception_data(
            "MoldingPricingRequest",
            [
                {
                    "type": "value_error",
                    "loc": ("cavities",),
                    "input": value,
                    "ctx": {"error": ValueError("cavities must be one of 1, 2, 4, 8, or auto")},
                }
            ],
        ) from exc
    if parsed not in {1, 2, 4, 8}:
        raise ValidationError.from_exception_data(
            "MoldingPricingRequest",
            [
                {
                    "type": "value_error",
                    "loc": ("cavities",),
                    "input": value,
                    "ctx": {"error": ValueError("cavities must be one of 1, 2, 4, 8, or auto")},
                }
            ],
        )
    return parsed


def _serializable_validation_errors(exc: ValidationError) -> list[dict]:
    errors = exc.errors()
    for error in errors:
        ctx = error.get("ctx")
        if isinstance(ctx, dict) and "error" in ctx:
            ctx["error"] = str(ctx["error"])
    return errors
