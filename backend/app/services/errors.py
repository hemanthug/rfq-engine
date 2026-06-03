from __future__ import annotations

from typing import Any


class UploadValidationError(Exception):
    code = "upload_validation_error"

    def __init__(self, message: str, **details: Any) -> None:
        super().__init__(message)
        self.message = message
        self.details = details

    def as_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "details": self.details}


class UploadFileMissingError(UploadValidationError):
    code = "upload_file_missing"


class UploadEmptyFileError(UploadValidationError):
    code = "upload_empty_file"


class UploadFileTooLargeError(UploadValidationError):
    code = "upload_file_too_large"


class UploadUnsupportedExtensionError(UploadValidationError):
    code = "cad_invalid_extension"
