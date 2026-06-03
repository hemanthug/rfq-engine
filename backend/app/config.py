from functools import lru_cache

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "RFQ Engine Backend"
    app_version: str = "0.1.0"
    environment: str = "development"
    docs_enabled: bool = True
    cad_allowed_extensions: tuple[str, ...] = (".step", ".stp")
    cad_max_file_size_bytes: int = 50 * 1024 * 1024
    cad_canonical_unit: str = "MM"
    cad_strict_solid: bool = True
    upload_max_file_size_bytes: int = 50 * 1024 * 1024
    upload_allowed_extensions: tuple[str, ...] = (".step", ".stp")
    upload_temp_dir: str | None = None
    preview_linear_deflection_mm: float = 0.5
    preview_angular_deflection_rad: float = 0.5
    preview_max_triangles: int = 250_000
    cors_allowed_origins: tuple[str, ...] = ("http://localhost:5173", "http://127.0.0.1:5173")

    model_config = ConfigDict(env_prefix="RFQ_", env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
