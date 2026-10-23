from datetime import datetime
from dataclasses import dataclass

from pydantic import Field

from app.shared.http.dto import RequestDTO, ResponseDTO


class DocumentResponse(ResponseDTO):
    id: int
    scope: str
    document_type: str
    title: str
    mime_type: str
    processing_status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class DocumentUploadRequest(RequestDTO):
    title: str | None = None
    document_type: str = Field(default="OTHER", max_length=50)


@dataclass(frozen=True)
class UploadedDocument:
    """HTTP-independent upload value passed into the document use case."""

    filename: str
    content_type: str
    content: bytes


__all__ = ["DocumentResponse", "DocumentUploadRequest", "UploadedDocument"]
