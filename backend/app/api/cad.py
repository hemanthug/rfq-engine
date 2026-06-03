from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from app.cad.errors import CadParseError, PreviewMeshTooLargeError
from app.config import Settings
from app.schemas.preview import CadPreviewWorkflowResult
from app.schemas.quote import ApiErrorResponse
from app.services.errors import UploadFileTooLargeError, UploadValidationError
from app.services.quote_workflow import QuoteWorkflowService


router = APIRouter()


@router.post(
    "/preview",
    response_model=CadPreviewWorkflowResult,
    responses={
        400: {"model": ApiErrorResponse},
        413: {"model": ApiErrorResponse},
        422: {"model": ApiErrorResponse},
    },
)
async def create_cad_preview(
    request: Request,
    file: UploadFile = File(...),
) -> CadPreviewWorkflowResult:
    settings: Settings = request.app.state.settings
    service = QuoteWorkflowService(settings)

    try:
        return await service.preview_cad(file)
    except UploadFileTooLargeError as exc:
        raise _http_error(413, exc.as_dict()) from exc
    except UploadValidationError as exc:
        raise _http_error(400, exc.as_dict()) from exc
    except PreviewMeshTooLargeError as exc:
        raise _http_error(422, exc.as_dict()) from exc
    except CadParseError as exc:
        raise _http_error(422, exc.as_dict()) from exc


def _http_error(status_code: int, error: dict) -> HTTPException:
    return HTTPException(status_code=status_code, detail=error)
