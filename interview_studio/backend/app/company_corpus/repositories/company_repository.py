from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.entity_registry import Company, Document, DocumentChunk


class CompanyRepository:
    """Read-only access to fixed company reference data."""
    def __init__(self, db: Session):
        self.db = db

    def by_name(self, name: str) -> Company | None:
        return self.db.scalar(select(Company).where(Company.name == name, Company.deleted_at.is_(None)))

    def get_or_create_active(self, name: str) -> Company:
        company = self.db.scalar(select(Company).where(Company.name == name))
        if company is None:
            company = Company(name=name)
            self.db.add(company)
            self.db.flush()
        elif company.deleted_at is not None:
            company.deleted_at = None
        return company

    def get(self, company_id: int) -> Company | None:
        return self.db.scalar(select(Company).where(Company.id == company_id, Company.deleted_at.is_(None)))

    def corpus_documents(self, company_id: int) -> list[Document]:
        return list(self.db.scalars(select(Document).where(Document.scope == "COMPANY", Document.company_id == company_id)))

    def delete_corpus(self, company_id: int) -> None:
        document_ids = select(Document.id).where(Document.scope == "COMPANY", Document.company_id == company_id)
        self.db.execute(delete(DocumentChunk).where(DocumentChunk.document_id.in_(document_ids)))
        self.db.execute(delete(Document).where(Document.scope == "COMPANY", Document.company_id == company_id))

    def replace_corpus_documents(self, company_id: int, sources) -> int:
        """Persist prepared fixed-corpus rows without committing the transaction."""
        self.delete_corpus(company_id)
        chunk_count = 0
        for source, source_chunks in sources:
            suffix = source.path.suffix.lower()
            document = Document(
                scope="COMPANY", user_id=None, company_id=company_id,
                document_type="INTERVIEW_RAG", title=source.path.stem,
                original_filename=source.path.name, file_path=str(source.path.resolve()),
                mime_type="text/markdown" if suffix == ".md" else "text/plain",
                extracted_text=source.text, processing_status="COMPLETED",
            )
            self.db.add(document)
            self.db.flush()
            for chunk_index, content, vector in source_chunks:
                self.db.add(DocumentChunk(
                    document_id=document.id, scope="COMPANY", user_id=None,
                    company_id=company_id, chunk_index=chunk_index, content=content,
                    metadata_json={"role_code": source.role_code}, embedding=vector,
                ))
                chunk_count += 1
        self.db.flush()
        return chunk_count
