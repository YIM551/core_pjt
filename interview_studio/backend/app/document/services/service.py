"""Document use-case service. Controllers only bind HTTP uploads."""

from sqlalchemy.orm import Session

from app.audit.repositories.audit_repository import AuditRepository
from app.auth.entities.models import User
from app.document.dto.models import UploadedDocument
from app.document.entities.models import Document
from app.document.exceptions import DocumentNotFound
from app.shared.utils.serialization import dump
from app.document.repositories.document_repository import DocumentRepository
from app.document.services.ingestion import chunks, extract_text, reprocess, store_upload
from app.shared.clients.file_storage import safe_delete


class DocumentService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = DocumentRepository(db)
        self.audit_repo = AuditRepository(db)

    def _audit(self, user: User, action: str, item: Document) -> None:
        self.audit_repo.record(
            actor_user_id=user.id,
            action=action,
            resource_type=item.__tablename__,
            resource_id=item.id,
            data_scope=item.scope,
            after_data=dump(item),
        )

    def list_personal(self, user: User):
        return self.repo.personal(user.id)

    def get_personal(self, user: User, document_id: int):
        item = self.repo.get_personal(document_id, user.id)
        if item is None:
            raise DocumentNotFound("document not found")
        return item

    def save_upload(self, user: User, upload: UploadedDocument, scope: str = "PERSONAL", title: str | None = None, document_type: str = "OTHER") -> Document:
        item: Document | None = None
        try:
            item = store_upload(self.db, upload, scope, user.id, None, title, document_type)
            self._audit(user, "CREATE", item)
            self.db.commit()
            self.db.refresh(item)
            return item
        except Exception:
            self.db.rollback()
            if item is not None:
                safe_delete(item.file_path)
            raise

    def reprocess(self, user: User, item: Document) -> Document:
        try:
            item = reprocess(self.db, item)
            self._audit(user, "REINDEX", item)
            self.db.commit()
            return item
        except Exception:
            self.db.rollback()
            raise

    def soft_delete(self, user: User, item: Document) -> None:
        try:
            self.repo.soft_delete(item)
            self._audit(user, "SOFT_DELETE", item)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise


__all__ = ["DocumentService", "reprocess", "store_upload", "extract_text", "chunks"]
