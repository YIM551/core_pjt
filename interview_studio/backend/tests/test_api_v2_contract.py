from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import app
from app.document.exceptions import (
    DocumentFileUnavailable,
    DocumentNotFound,
    InvalidUploadFilename,
    UnsupportedDocumentType,
    UploadTooLarge,
)
from app.interview.controllers import controller as interview_controller
from app.shared.http.problems import domain_exception_handler


def test_only_v2_business_routes_are_registered():
    paths = set(app.openapi()["paths"])
    assert "/api/v1/auth/login" not in paths
    assert "/api/v2/auth/session" in paths
    assert "/api/v2/candidate/profile" not in paths
    assert "/api/v2/candidate/projects" not in paths
    assert "/api/v2/candidate/documents" in paths
    assert "/api/v2/candidate/chat" in paths
    assert "/api/v2/interviews/{session_id}/messages/stream" in paths


def test_problem_details_have_rfc9457_shape():
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/v2/candidate/profile")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    assert set(response.json()) == {"type", "title", "status", "detail", "code", "errors"}
    assert response.json()["code"] == "RESOURCE_NOT_FOUND"


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/v2/candidate/profile"),
        ("put", "/api/v2/candidate/profile"),
        ("get", "/api/v2/candidate/projects"),
        ("post", "/api/v2/candidate/projects"),
        ("get", "/api/v2/candidate/projects/1"),
        ("patch", "/api/v2/candidate/projects/1"),
        ("delete", "/api/v2/candidate/projects/1"),
        ("post", "/api/v2/candidate/projects/1/restore"),
    ],
)
def test_removed_profile_and_project_routes_return_problem_details(method, path):
    response = getattr(TestClient(app, raise_server_exceptions=False), method)(path)
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "RESOURCE_NOT_FOUND"


def test_interview_stream_uses_real_sse_newlines(monkeypatch):
    class FakeInterviewService:
        def __init__(self, db, user):
            pass

        def prepare_message(self, session_id, payload):
            return SimpleNamespace(
                result=SimpleNamespace(interviewer_reply="hello"),
            )

        def persist_message(self, prepared):
            return {"interviewer_message": {"content": "hello"}}

        def rollback(self):
            pass

    monkeypatch.setattr(
        interview_controller,
        "InterviewService",
        FakeInterviewService,
    )
    test_app = FastAPI()
    test_app.include_router(interview_controller.router)
    test_app.dependency_overrides[interview_controller.get_db] = lambda: object()
    test_app.dependency_overrides[interview_controller.current_user] = lambda: object()

    response = TestClient(test_app).post(
        "/interviews/1/messages/stream",
        json={"content": "hi"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert 'event: status\ndata: {"step": "generating"}\n\n' in response.text
    assert 'event: token\ndata: {"text": "hello"}\n\n' in response.text
    assert (
        'event: complete\ndata: {"interviewer_message": {"content": "hello"}}\n\n'
        in response.text
    )
    assert "\\ndata:" not in response.text
    assert "\\n\\n" not in response.text


def test_interview_stream_error_frame_uses_real_sse_newlines(monkeypatch):
    class FailingInterviewService:
        def __init__(self, db, user):
            pass

        def prepare_message(self, session_id, payload):
            return SimpleNamespace(
                result=SimpleNamespace(interviewer_reply="hello"),
            )

        def persist_message(self, prepared):
            raise RuntimeError("persist failed")

        def rollback(self):
            pass

    monkeypatch.setattr(
        interview_controller,
        "InterviewService",
        FailingInterviewService,
    )
    test_app = FastAPI()
    test_app.include_router(interview_controller.router)
    test_app.dependency_overrides[interview_controller.get_db] = lambda: object()
    test_app.dependency_overrides[interview_controller.current_user] = lambda: object()

    response = TestClient(test_app).post(
        "/interviews/1/messages/stream",
        json={"content": "hi"},
    )

    assert response.status_code == 200
    assert 'event: error\ndata: {"code":"INTERNAL_ERROR"}\n\n' in response.text
    assert "\\ndata:" not in response.text
    assert "\\n\\n" not in response.text


@pytest.mark.parametrize(
    ("error", "expected_status", "expected_code"),
    [
        (DocumentNotFound("document not found"), 404, "RESOURCE_NOT_FOUND"),
        (
            DocumentFileUnavailable("stored file unavailable"),
            409,
            "DOCUMENT_FILE_UNAVAILABLE",
        ),
        (InvalidUploadFilename("Invalid upload filename."), 400, "REQUEST_ERROR"),
        (UnsupportedDocumentType("unsupported"), 415, "REQUEST_ERROR"),
        (UploadTooLarge("too large"), 413, "REQUEST_ERROR"),
    ],
)
def test_domain_failures_keep_problem_details_contract(
    error,
    expected_status,
    expected_code,
):
    test_app = FastAPI()
    test_app.add_exception_handler(type(error).__bases__[0], domain_exception_handler)

    @test_app.get("/failure")
    def failure():
        raise error

    result = TestClient(test_app).get("/failure")
    assert result.status_code == expected_status
    assert result.headers["content-type"].startswith("application/problem+json")
    assert result.json()["code"] == expected_code
