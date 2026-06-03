import sys

from fastapi import APIRouter, Request

from app.config import Settings
from app.schemas.health import LivenessResponse, ReadinessResponse


router = APIRouter()


@router.get("/live", response_model=LivenessResponse)
def live() -> LivenessResponse:
    return LivenessResponse(status="ok")


@router.get("/ready", response_model=ReadinessResponse)
def ready(request: Request) -> ReadinessResponse:
    settings: Settings = request.app.state.settings
    return ReadinessResponse(
        status="ok",
        ready=True,
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        python_version=sys.version.split()[0],
    )

