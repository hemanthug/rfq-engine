from __future__ import annotations

import re
import tempfile
import time
from pathlib import Path

from fastapi import UploadFile

from app.cad.preview_mesh import PreviewMeshBuilder
from app.cad.step_reader import StepReader
from app.config import Settings, get_settings
from app.pricing.cnc import CncBudgetaryPricer
from app.pricing.molding import MoldingBudgetaryPricer
from app.pricing.sheet_metal import SheetMetalBudgetaryPricer
from app.schemas.preview import CadPreviewUploadMetadata, CadPreviewWorkflowMetadata, CadPreviewWorkflowResult
from app.schemas.pricing import CncPricingRequest, MoldingPricingRequest, SheetMetalPricingRequest
from app.schemas.quote import (
    MoldingQuoteWorkflowResult,
    QuoteUploadMetadata,
    QuoteWorkflowMetadata,
    QuoteWorkflowResult,
    SheetMetalQuoteWorkflowResult,
)
from app.services.process_fit import ProcessFitRecommender
from app.services.errors import (
    UploadEmptyFileError,
    UploadFileMissingError,
    UploadFileTooLargeError,
    UploadUnsupportedExtensionError,
)
from app.cad.feature_extractor import FeatureExtractor


SAFE_FILENAME_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")


class QuoteWorkflowService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.step_reader = StepReader(self.settings)
        self.feature_extractor = FeatureExtractor(self.step_reader)
        self.preview_builder = PreviewMeshBuilder(self.settings)
        self.pricer = CncBudgetaryPricer()
        self.molding_pricer = MoldingBudgetaryPricer()
        self.sheet_metal_pricer = SheetMetalBudgetaryPricer()
        self.process_fit_recommender = ProcessFitRecommender()

    async def preview_cad(self, upload: UploadFile) -> CadPreviewWorkflowResult:
        started_at = time.perf_counter()
        sanitized_filename = self._sanitize_filename(upload.filename)
        extension = self._validate_extension(sanitized_filename)

        with tempfile.TemporaryDirectory(prefix="rfq-upload-", dir=self.settings.upload_temp_dir) as temp_dir:
            upload_path = Path(temp_dir) / sanitized_filename
            size_bytes = await self._write_upload(upload, upload_path)
            context = self.step_reader.load_context(upload_path)
            features = self.feature_extractor.extract_from_context(context)
            preview = self.preview_builder.build(context.shape, context.parse_result.bounding_box)
            process_fit = self.process_fit_recommender.recommend(features)

        elapsed_ms = (time.perf_counter() - started_at) * 1000.0
        return CadPreviewWorkflowResult(
            preview=preview,
            source=context.parse_result,
            process_fit=process_fit,
            upload=CadPreviewUploadMetadata(
                filename=sanitized_filename,
                size_bytes=size_bytes,
                extension=extension,
            ),
            workflow=CadPreviewWorkflowMetadata(
                schema_version="1.0",
                elapsed_ms=round(elapsed_ms, 2),
            ),
        )

    async def quote_cnc(self, upload: UploadFile, pricing_request: CncPricingRequest) -> QuoteWorkflowResult:
        started_at = time.perf_counter()
        sanitized_filename = self._sanitize_filename(upload.filename)
        extension = self._validate_extension(sanitized_filename)

        with tempfile.TemporaryDirectory(prefix="rfq-upload-", dir=self.settings.upload_temp_dir) as temp_dir:
            upload_path = Path(temp_dir) / sanitized_filename
            size_bytes = await self._write_upload(upload, upload_path)
            context = self.step_reader.load_context(upload_path)
            features = self.feature_extractor.extract_from_context(context)
            preview = self.preview_builder.build(context.shape, context.parse_result.bounding_box)
            quote = self.pricer.price(features, pricing_request)

        elapsed_ms = (time.perf_counter() - started_at) * 1000.0
        return QuoteWorkflowResult(
            quote=quote,
            preview=preview,
            upload=QuoteUploadMetadata(
                filename=sanitized_filename,
                size_bytes=size_bytes,
                extension=extension,
            ),
            workflow=QuoteWorkflowMetadata(
                schema_version="1.0",
                elapsed_ms=round(elapsed_ms, 2),
            ),
        )

    async def quote_injection_molding(
        self,
        upload: UploadFile,
        pricing_request: MoldingPricingRequest,
    ) -> MoldingQuoteWorkflowResult:
        started_at = time.perf_counter()
        sanitized_filename = self._sanitize_filename(upload.filename)
        extension = self._validate_extension(sanitized_filename)

        with tempfile.TemporaryDirectory(prefix="rfq-upload-", dir=self.settings.upload_temp_dir) as temp_dir:
            upload_path = Path(temp_dir) / sanitized_filename
            size_bytes = await self._write_upload(upload, upload_path)
            context = self.step_reader.load_context(upload_path)
            features = self.feature_extractor.extract_from_context(context)
            preview = self.preview_builder.build(context.shape, context.parse_result.bounding_box)
            quote = self.molding_pricer.price(features, pricing_request)

        elapsed_ms = (time.perf_counter() - started_at) * 1000.0
        return MoldingQuoteWorkflowResult(
            quote=quote,
            preview=preview,
            upload=QuoteUploadMetadata(
                filename=sanitized_filename,
                size_bytes=size_bytes,
                extension=extension,
            ),
            workflow=QuoteWorkflowMetadata(
                schema_version="1.0",
                elapsed_ms=round(elapsed_ms, 2),
            ),
        )

    async def quote_sheet_metal(
        self,
        upload: UploadFile,
        pricing_request: SheetMetalPricingRequest,
    ) -> SheetMetalQuoteWorkflowResult:
        started_at = time.perf_counter()
        sanitized_filename = self._sanitize_filename(upload.filename)
        extension = self._validate_extension(sanitized_filename)

        with tempfile.TemporaryDirectory(prefix="rfq-upload-", dir=self.settings.upload_temp_dir) as temp_dir:
            upload_path = Path(temp_dir) / sanitized_filename
            size_bytes = await self._write_upload(upload, upload_path)
            context = self.step_reader.load_context(upload_path)
            features = self.feature_extractor.extract_from_context(context)
            preview = self.preview_builder.build(context.shape, context.parse_result.bounding_box)
            quote = self.sheet_metal_pricer.price(features, pricing_request)

        elapsed_ms = (time.perf_counter() - started_at) * 1000.0
        return SheetMetalQuoteWorkflowResult(
            quote=quote,
            preview=preview,
            upload=QuoteUploadMetadata(
                filename=sanitized_filename,
                size_bytes=size_bytes,
                extension=extension,
            ),
            workflow=QuoteWorkflowMetadata(
                schema_version="1.0",
                elapsed_ms=round(elapsed_ms, 2),
            ),
        )

    def _sanitize_filename(self, filename: str | None) -> str:
        if not filename:
            raise UploadFileMissingError("Uploaded file is missing a filename.")
        safe_name = SAFE_FILENAME_PATTERN.sub("_", Path(filename).name).strip("._")
        if not safe_name:
            raise UploadFileMissingError("Uploaded file has an invalid filename.")
        return safe_name

    def _validate_extension(self, filename: str) -> str:
        extension = Path(filename).suffix.lower()
        if extension not in self.settings.upload_allowed_extensions:
            raise UploadUnsupportedExtensionError(
                "Uploaded CAD file extension is not supported.",
                filename=filename,
                extension=extension,
                allowed_extensions=list(self.settings.upload_allowed_extensions),
            )
        return extension

    async def _write_upload(self, upload: UploadFile, upload_path: Path) -> int:
        size_bytes = 0
        with upload_path.open("wb") as output:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                size_bytes += len(chunk)
                if size_bytes > self.settings.upload_max_file_size_bytes:
                    raise UploadFileTooLargeError(
                        "Uploaded file exceeds the configured upload size limit.",
                        size_bytes=size_bytes,
                        max_file_size_bytes=self.settings.upload_max_file_size_bytes,
                    )
                output.write(chunk)
        if size_bytes <= 0:
            raise UploadEmptyFileError("Uploaded file is empty.")
        return size_bytes
