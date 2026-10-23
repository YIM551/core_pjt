from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pytest

from app.core.database import Base
from app.core import entity_registry  # noqa: F401
from app.auth.entities.models import User
from app.auth.services.service import AuthService
from app.document.entities.models import Document
from app.document.services.service import DocumentService
from app.document.exceptions import DocumentNotFound
from app.document.dto.models import UploadedDocument
from app.company_corpus.entities.models import Company
from app.interview.dto.models import InterviewCreateRequest, InterviewMessageRequest
from app.interview.services.service import InterviewService
from app.interview.exceptions import InterviewNotFound
from app.interview.dto.models import InterviewTurnResult


def test_temporary_auth_session_round_trip():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    service = AuthService(db)
    user = service.temporary_user()
    assert service.resolve_session(service.issue_session(user)) == user.id


def test_document_soft_delete_hides_path_and_owner_scope():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    owner, other = User(email="doc-owner@test", name="owner"), User(email="doc-other@test", name="other")
    db.add_all([owner, other]); db.commit()
    doc = Document(scope="PERSONAL", user_id=owner.id, company_id=None, document_type="OTHER", title="resume", original_filename="resume.txt", file_path="/private/uploads/resume.txt", mime_type="text/plain", processing_status="COMPLETED")
    db.add(doc); db.commit()
    service = DocumentService(db)
    assert service.get_personal(owner, doc.id).file_path.startswith("/private/")
    try:
        service.get_personal(other, doc.id)
        assert False, "foreign user must not access a document"
    except DocumentNotFound:
        pass
    service.soft_delete(owner, doc)
    assert service.list_personal(owner) == []


def test_uploaded_filename_is_not_used_as_default_display_title(
    monkeypatch,
    tmp_path,
):
    from types import SimpleNamespace
    from app.document.services import ingestion

    created = {}
    chunk_metadata = {}

    class Repository:
        def __init__(self, _):
            pass

        def create_document(self, **values):
            created.update(values)
            return SimpleNamespace(id=1, **values)

        def mark_completed(self, document, text):
            document.extracted_text = text
            document.processing_status = "COMPLETED"

        def replace_chunks(self, document, values, metadata):
            list(values)
            chunk_metadata.update(metadata)

    monkeypatch.setattr(ingestion, "DocumentRepository", Repository)
    monkeypatch.setattr(
        ingestion,
        "get_settings",
        lambda: SimpleNamespace(max_upload_mb=10, upload_dir=tmp_path),
    )
    monkeypatch.setattr(
        ingestion,
        "_document_vectors",
        lambda parts: [[0.0] * 768 for _ in parts],
    )

    document = ingestion.store_upload(
        object(),
        UploadedDocument(
            filename="private-resume-name.txt",
            content_type="text/plain",
            content=b"safe candidate content",
        ),
        "PERSONAL",
        1,
        None,
        None,
        "OTHER",
    )

    assert document.title == "개인 문서"
    assert created["original_filename"] == "private-resume-name.txt"
    assert "filename" not in chunk_metadata


def test_interview_create_message_finish_report_and_owner_scope(monkeypatch):
    engine = create_engine("sqlite://"); Base.metadata.create_all(engine); db = sessionmaker(bind=engine)()
    owner, other = User(email="i-owner@test", name="o"), User(email="i-other@test", name="x")
    company = Company(name="삼성전자")
    db.add_all([owner, other, company]); db.commit()
    monkeypatch.setattr("app.interview.services.agent.run_interview_turn", lambda *a, **k: InterviewTurnResult(intent="ANSWER", interviewer_reply="reply", next_phase="INTERVIEW"))
    service = InterviewService(db, owner)
    created = service.create(InterviewCreateRequest(target_role="BACKEND"))
    session_id = created["session"]["id"]
    turn = service.send(session_id, InterviewMessageRequest(content="answer"))
    assert turn["interviewer_message"]["content"] == "reply"
    monkeypatch.setattr("app.interview.services.agent.run_interview_report", lambda **_: "summary")
    finished = service.finish(session_id)
    assert finished["status"] == "COMPLETED"
    assert service.report(session_id)["summary"] is None
    with pytest.raises(InterviewNotFound):
        InterviewService(db, other).detail(session_id)
