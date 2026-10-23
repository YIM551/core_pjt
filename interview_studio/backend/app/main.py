from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import get_settings
from app.core.observability import configure_audit_logging
from app.auth.controllers.controller import router as auth_router
from app.candidate.controllers.controller import router as candidate_router
from app.document.controllers.controller import router as document_router
from app.interview.controllers.controller import router as interview_router
from app.studio.controller import router as studio_router
from app.interview.exceptions import InterviewDomainError
from app.document.exceptions import DocumentDomainError
from app.shared.ai.runtime import ToolCallingUnavailable
from app.shared.http.problems import (
    EmbeddingServiceError,
    Problem,
    RequestValidationError,
    embedding_exception_handler,
    domain_exception_handler,
    http_exception_handler,
    problem_exception_handler,
    tool_calling_exception_handler,
    unexpected_exception_handler,
    validation_exception_handler,
)

configure_audit_logging()
settings = get_settings()
app = FastAPI(title="CareerFit AI API", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[], allow_origin_regex=settings.cors_allowed_origin_regex,
    allow_credentials=True, allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Accept", "Authorization", "Content-Type", "X-Requested-With", "Idempotency-Key", "X-Capture-Generation", "X-Media-Start-Ms", "X-Media-End-Ms"],
)
app.add_exception_handler(Problem, problem_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(EmbeddingServiceError, embedding_exception_handler)
app.add_exception_handler(ToolCallingUnavailable, tool_calling_exception_handler)
app.add_exception_handler(InterviewDomainError, domain_exception_handler)
app.add_exception_handler(DocumentDomainError, domain_exception_handler)
app.add_exception_handler(Exception, unexpected_exception_handler)

app.include_router(auth_router, prefix="/api/v2")
app.include_router(candidate_router, prefix="/api/v2")
app.include_router(document_router, prefix="/api/v2")
app.include_router(interview_router, prefix="/api/v2")
app.include_router(studio_router, prefix="/api/v2")


@app.get("/health")
def health():
    return {"status": "ok"}

