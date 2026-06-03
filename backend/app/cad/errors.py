from pathlib import Path
from typing import Any


class CadParseError(Exception):
    code = "cad_parse_error"

    def __init__(self, message: str, path: str | Path | None = None, **details: Any) -> None:
        super().__init__(message)
        self.message = message
        self.path = str(path) if path is not None else None
        self.details = details

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "path": self.path,
            "details": self.details,
        }


class CadFileMissingError(CadParseError):
    code = "cad_file_missing"


class CadFileNotRegularError(CadParseError):
    code = "cad_file_not_regular"


class CadFileTooLargeError(CadParseError):
    code = "cad_file_too_large"


class CadInvalidExtensionError(CadParseError):
    code = "cad_invalid_extension"


class StepReadError(CadParseError):
    code = "step_read_failed"


class StepTransferError(CadParseError):
    code = "step_transfer_failed"


class StepNullShapeError(CadParseError):
    code = "step_null_shape"


class StepUnsupportedShapeError(CadParseError):
    code = "step_unsupported_shape"


class PreviewMeshError(CadParseError):
    code = "preview_mesh_failed"


class PreviewMeshTooLargeError(CadParseError):
    code = "preview_mesh_too_large"
