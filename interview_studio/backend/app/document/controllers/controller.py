from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import current_user
from app.document.dto.models import (
    DocumentResponse,
    DocumentUploadRequest,
    UploadedDocument,
)
from app.document.services.service import DocumentService

router = APIRouter(prefix="/candidate/documents", tags=["documents"])


def _response(item):
    return DocumentResponse(
        id=item.id, scope=item.scope, document_type=item.document_type, title=item.title,
        mime_type=item.mime_type,
        processing_status=item.processing_status, created_at=item.created_at, updated_at=item.updated_at,
    )


@router.get("", response_model=list[DocumentResponse])
def list_documents(db: Session = Depends(get_db), user = Depends(current_user)):
    return [_response(item) for item in DocumentService(db).list_personal(user)]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=DocumentResponse)
def upload_document(file: UploadFile = File(...), title: str | None = Form(None), document_type: str = Form("OTHER"), db: Session = Depends(get_db), user = Depends(current_user)):
    payload = DocumentUploadRequest(title=title, document_type=document_type)
    upload = UploadedDocument(
        filename=file.filename or "upload",
        content_type=file.content_type or "application/octet-stream",
        content=file.file.read(),
    )
    return _response(DocumentService(db).save_upload(user, upload, title=payload.title, document_type=payload.document_type))


@router.post("/{document_id}/reprocess", response_model=DocumentResponse)
def reprocess_document(document_id: int, db: Session = Depends(get_db), user = Depends(current_user)):
    service = DocumentService(db)
    return _response(service.reprocess(user, service.get_personal(user, document_id)))


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: int, db: Session = Depends(get_db), user = Depends(current_user)):
    service = DocumentService(db)
    service.soft_delete(user, service.get_personal(user, document_id))
