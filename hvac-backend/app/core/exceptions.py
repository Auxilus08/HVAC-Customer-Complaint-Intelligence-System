"""Custom exception classes and FastAPI exception handlers."""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

logger = get_logger(__name__)


class HVACBaseException(Exception):
    """Base exception for all domain errors."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    detail: str = "An unexpected error occurred"

    def __init__(self, detail: str | None = None) -> None:
        self.detail = detail or self.__class__.detail
        super().__init__(self.detail)


class ComplaintNotFoundError(HVACBaseException):
    status_code = status.HTTP_404_NOT_FOUND
    detail = "Complaint not found"


class ClusterNotFoundError(HVACBaseException):
    status_code = status.HTTP_404_NOT_FOUND
    detail = "Cluster not found"


class ValidationError(HVACBaseException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    detail = "Validation failed"


class EmbeddingServiceError(HVACBaseException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    detail = "Embedding service unavailable"


class ClusteringJobError(HVACBaseException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    detail = "Clustering job failed"


class AdvisoryServiceError(HVACBaseException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    detail = "Advisory generation failed"


class PIIStripError(HVACBaseException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    detail = "PII stripping pipeline failed"


class EncryptionError(HVACBaseException):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    detail = "Encryption/decryption failed"


def register_exception_handlers(app: FastAPI) -> None:
    """Attach all exception handlers to the FastAPI app."""

    @app.exception_handler(HVACBaseException)
    async def hvac_exception_handler(
        request: Request, exc: HVACBaseException
    ) -> JSONResponse:
        logger.warning(
            "domain_exception",
            exc_type=type(exc).__name__,
            detail=exc.detail,
            path=request.url.path,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": type(exc).__name__, "detail": exc.detail},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception(
            "unhandled_exception",
            exc_type=type(exc).__name__,
            path=request.url.path,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "InternalServerError",
                "detail": "An unexpected error occurred",
            },
        )
