from pydantic import BaseModel, Field


class LivenessResponse(BaseModel):
    status: str = Field(description="Liveness status for the backend process.")


class ReadinessResponse(BaseModel):
    status: str = Field(description="Readiness status for the backend process.")
    ready: bool = Field(description="Whether the backend process is ready to serve requests.")
    service: str
    version: str
    environment: str
    python_version: str


class ServiceInfoResponse(BaseModel):
    service: str
    version: str
    environment: str
    python_version: str

