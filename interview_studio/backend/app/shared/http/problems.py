from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.shared.clients.embedding import EmbeddingServiceError
from app.shared.ai.runtime import ToolCallingUnavailable
from app.document.exceptions import (
    DocumentDomainError,
    DocumentFileUnavailable,
    DocumentNotFound,
    InvalidUploadFilename,
    UnsupportedDocumentType,
    UploadTooLarge,
)
from app.interview.exceptions import InterviewDomainError


class Problem(HTTPException):
    def __init__(self, status: int, code: str, detail: str, *, errors: list[dict[str, Any]] | None = None):
        super().__init__(status_code=status, detail=detail)
        self.code = code
        self.errors = errors or []


def response(status: int, code: str, detail: str, errors: list[dict[str, Any]] | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        media_type="application/problem+json",
        content={
            "type": f"urn:careerfit:problem:{code.lower()}",
            "title": code.replace("_", " ").title(),
            "status": status,
            "detail": detail,
            "code": code,
            "errors": errors or [],
        },
    )


async def problem_exception_handler(_: Request, exc: Problem) -> JSONResponse:
    return response(exc.status_code, exc.code, str(exc.detail), exc.errors)


async def http_exception_handler(
    _: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    code = "LLM_TOOL_CALLING_UNAVAILABLE" if str(exc.detail) == "LLM_TOOL_CALLING_UNAVAILABLE" else "REQUEST_ERROR"
    if exc.status_code == 401:
        code = "AUTHENTICATION_REQUIRED"
    elif exc.status_code == 404:
        code = "RESOURCE_NOT_FOUND"
    elif exc.status_code == 409:
        code = "RESOURCE_CONFLICT"
    return response(exc.status_code, code, str(exc.detail))


async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return response(422, "VALIDATION_ERROR", "요청 값이 올바르지 않습니다.", exc.errors())


async def domain_exception_handler(
    _: Request,
    exc: DocumentDomainError | InterviewDomainError,
) -> JSONResponse:
    """Translate transport-agnostic use-case failures at the HTTP boundary."""
    if isinstance(exc, InterviewDomainError):
        return response(exc.status, exc.code, exc.detail)
    if isinstance(exc, DocumentNotFound):
        return response(404, "RESOURCE_NOT_FOUND", str(exc))
    if isinstance(exc, DocumentFileUnavailable):
        return response(409, "DOCUMENT_FILE_UNAVAILABLE", str(exc))
    if isinstance(exc, InvalidUploadFilename):
        return response(400, "REQUEST_ERROR", str(exc))
    if isinstance(exc, UnsupportedDocumentType):
        return response(415, "REQUEST_ERROR", str(exc))
    if isinstance(exc, UploadTooLarge):
        return response(413, "REQUEST_ERROR", str(exc))
    return response(400, "REQUEST_ERROR", str(exc))


async def embedding_exception_handler(_: Request, __: EmbeddingServiceError) -> JSONResponse:
    return response(503, "EMBEDDING_SERVICE_UNAVAILABLE", "임베딩 서비스를 사용할 수 없습니다.")


async def tool_calling_exception_handler(_: Request, __: ToolCallingUnavailable) -> JSONResponse:
    return response(503, "LLM_TOOL_CALLING_UNAVAILABLE", "LLM tool calling is unavailable.")


async def unexpected_exception_handler(_: Request, __: Exception) -> JSONResponse:
    return response(500, "INTERNAL_ERROR", "서버 오류가 발생했습니다.")
