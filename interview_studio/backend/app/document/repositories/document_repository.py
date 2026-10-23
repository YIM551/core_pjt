from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.core.entity_registry import Document, DocumentChunk


class DocumentRepository:
    def __init__(self, db: Session):
        self.db = db

    def personal(self, user_id: int) -> list[Document]:
        return list(self.db.scalars(select(Document).where(Document.scope == "PERSONAL", Document.user_id == user_id, Document.deleted_at.is_(None))).all())

    def create_document(self, **values) -> Document:
        document = Document(**values)
        self.db.add(document)
        self.db.flush()
        return document

    def get_personal(self, document_id: int, user_id: int) -> Document | None:
        return self.db.scalar(select(Document).where(Document.id == document_id, Document.scope == "PERSONAL", Document.user_id == user_id, Document.deleted_at.is_(None)))

    def chunks_for(self, document_id: int) -> list[DocumentChunk]:
        return list(self.db.scalars(select(DocumentChunk).where(DocumentChunk.document_id == document_id, DocumentChunk.deleted_at.is_(None)).order_by(DocumentChunk.chunk_index)).all())

    def delete_chunks(self, document_id: int) -> None:
        self.db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))

    def replace_chunks(self, document: Document, chunks_with_embeddings, metadata: dict) -> None:
        self.delete_chunks(document.id)
        for index, (content, embedding) in enumerate(chunks_with_embeddings):
            self.db.add(DocumentChunk(document_id=document.id, scope=document.scope, user_id=document.user_id, company_id=document.company_id, chunk_index=index, content=content, metadata_json=metadata.copy(), embedding=embedding))
        self.db.flush()

    def mark_processing(self, document: Document) -> None:
        document.processing_status = "PROCESSING"

    def mark_failed(self, document: Document) -> None:
        self.delete_chunks(document.id)
        document.extracted_text = None
        document.processing_status = "FAILED"

    def mark_completed(self, document: Document, extracted_text: str) -> None:
        document.extracted_text = extracted_text
        document.processing_status = "COMPLETED"

    def soft_delete(self, document: Document) -> None:
        document.deleted_at = datetime.now(timezone.utc)

    def vector_rows(self, scope: str, vector, *, user_id: int | None = None, company_id: int | None = None, role_code: str | None = None, limit: int = 12):
        distance = DocumentChunk.embedding.cosine_distance(vector).label("distance")
        stmt = select(DocumentChunk, Document, distance).join(Document, Document.id == DocumentChunk.document_id).where(
            DocumentChunk.scope == scope, Document.scope == scope, DocumentChunk.deleted_at.is_(None), Document.deleted_at.is_(None),
            Document.processing_status == "COMPLETED", DocumentChunk.embedding.is_not(None),
        )
        if scope == "PERSONAL":
            stmt = stmt.where(DocumentChunk.user_id == user_id, Document.user_id == user_id, DocumentChunk.company_id.is_(None), Document.company_id.is_(None))
        else:
            stmt = stmt.where(DocumentChunk.company_id == company_id, Document.company_id == company_id, DocumentChunk.user_id.is_(None), Document.user_id.is_(None))
        if role_code is not None:
            stmt = stmt.where(DocumentChunk.metadata_json["role_code"].as_string() == role_code)
        return self.db.execute(stmt.order_by(distance).limit(limit))
