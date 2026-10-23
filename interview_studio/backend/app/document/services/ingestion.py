import csv
import io
import json
import fitz
from docx import Document as DocxDocument
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.entity_registry import Document
from app.shared.clients.embedding import (
    EmbeddingServiceError,
    embed_documents,
    embedding,
    embedding_metadata,
)
from app.document.repositories.document_repository import DocumentRepository
from app.document.dto.models import UploadedDocument
from app.document.exceptions import (
    DocumentFileUnavailable,
    InvalidUploadFilename,
    UnsupportedDocumentType,
    UploadTooLarge,
)
from app.shared.clients.file_storage import (
    UnsafeStoredUploadPath,
    UnsafeUploadName,
    describe_upload,
    read_bytes,
    safe_delete,
    write_upload,
)

ALLOWED_SUFFIXES = {".pdf", ".docx", ".txt", ".md", ".markdown", ".csv", ".json"}
_DEFAULT_EMBEDDING = embedding


def extract_text(content: bytes, suffix: str) -> str:
    if suffix == ".pdf":
        pdf = fitz.open(stream=content, filetype="pdf")
        return "\n".join(page.get_text() for page in pdf)
    if suffix == ".docx":
        doc = DocxDocument(io.BytesIO(content))
        return "\n".join(p.text for p in doc.paragraphs)
    if suffix == ".csv":
        return "\n".join(" | ".join(row) for row in csv.reader(io.StringIO(content.decode("utf-8-sig"))))
    if suffix == ".json":
        return json.dumps(json.loads(content.decode("utf-8")), ensure_ascii=False, indent=2)
    return content.decode("utf-8", errors="replace")


def chunks(text: str, size: int = 900, overlap: int = 150):
    text = " ".join(text.split())
    for start in range(0, len(text), size - overlap):
        piece = text[start:start + size]
        if piece:
            yield piece


def _document_vectors(items: list[str]) -> list[list[float]]:
    # Preserve the long-standing unit-test seam while production uses batch calls.
    if embedding is not _DEFAULT_EMBEDDING:
        return [embedding(item) for item in items]
    return embed_documents(items)


def _chunk_metadata(document: Document) -> dict:
    return {"title": document.title, **embedding_metadata("document")}


def store_upload(db: Session, upload: UploadedDocument, scope: str, user_id: int | None, company_id: int | None, title: str | None, document_type: str):
    filename = upload.filename or "upload"
    try:
        original_filename, suffix = describe_upload(filename)
    except UnsafeUploadName as exc:
        raise InvalidUploadFilename("Invalid upload filename.") from exc
    if suffix not in ALLOWED_SUFFIXES:
        raise UnsupportedDocumentType("지원하지 않는 문서 형식입니다.")
    content = upload.content
    if len(content) > get_settings().max_upload_mb * 1024 * 1024:
        raise UploadTooLarge("파일 크기 제한을 초과했습니다.")
    root = get_settings().upload_dir / scope.lower()
    try:
        stored = write_upload(root, original_filename, content)
    except UnsafeUploadName as exc:
        raise InvalidUploadFilename("Invalid upload filename.") from exc
    repository = DocumentRepository(db)
    try:
        doc = repository.create_document(
            scope=scope,
            user_id=user_id,
            company_id=company_id,
            document_type=document_type,
            title=title or "개인 문서",
            original_filename=stored.original_filename,
            file_path=stored.path,
            mime_type=upload.content_type or "application/octet-stream",
            processing_status="PROCESSING",
        )
    except Exception:
        safe_delete(stored.path)
        raise

    try:
        text = extract_text(content, suffix)
        parts = list(chunks(text))
        if not parts:
            raise ValueError("Document contains no extractable text.")
    except Exception:
        # Ordinary parsing failures remain visible as a terminal document state.
        repository.mark_failed(doc)
        return doc

    try:
        vectors = _document_vectors(parts)
    except EmbeddingServiceError:
        safe_delete(stored.path)
        raise

    repository.mark_completed(doc, text)
    repository.replace_chunks(doc, zip(parts, vectors, strict=True), _chunk_metadata(doc))
    return doc


def reprocess(db: Session, document: Document):
    repository = DocumentRepository(db)
    repository.mark_processing(document)
    try:
        content = read_bytes(get_settings().upload_dir, document.file_path)
    except (FileNotFoundError, UnsafeStoredUploadPath) as exc:
        raise DocumentFileUnavailable(
            "The stored document file is unavailable."
        ) from exc
    _, suffix = describe_upload(document.original_filename)
    try:
        text = extract_text(content, suffix)
        parts = list(chunks(text))
        if not parts:
            raise ValueError("Document contains no extractable text.")
    except Exception:
        repository.mark_failed(document)
        return document
    vectors = _document_vectors(parts)
    repository.mark_completed(document, text)
    repository.replace_chunks(
        document,
        zip(parts, vectors, strict=True),
        _chunk_metadata(document),
    )
    return document
