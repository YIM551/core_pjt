from pathlib import Path
from types import SimpleNamespace

import pytest

from app.document.exceptions import DocumentFileUnavailable
from app.document.services import ingestion
from app.shared.clients.file_storage import (
    UnsafeStoredUploadPath,
    read_bytes,
    resolve_upload_path,
)


def test_legacy_docker_path_resolves_under_configured_upload_root(tmp_path):
    upload = tmp_path / "personal" / "resume.md"
    upload.parent.mkdir()
    upload.write_bytes(b"candidate")

    assert (
        resolve_upload_path(tmp_path, "/app/uploads/personal/resume.md")
        == upload.resolve()
    )
    assert (
        read_bytes(tmp_path, "/app/uploads/personal/resume.md")
        == b"candidate"
    )


@pytest.mark.parametrize(
    "stored_path",
    [
        "/app/uploads/../../etc/passwd",
        "/private/uploads/resume.md",
        "../../outside.md",
    ],
)
def test_stored_path_cannot_escape_configured_upload_root(tmp_path, stored_path):
    with pytest.raises(UnsafeStoredUploadPath):
        resolve_upload_path(tmp_path, stored_path)


def test_reprocess_reports_missing_stored_file_as_domain_failure(
    monkeypatch,
    tmp_path,
):
    class Repository:
        def __init__(self, _):
            pass

        def mark_processing(self, document):
            document.processing_status = "PROCESSING"

    monkeypatch.setattr(ingestion, "DocumentRepository", Repository)
    monkeypatch.setattr(
        ingestion,
        "get_settings",
        lambda: SimpleNamespace(upload_dir=tmp_path),
    )
    document = SimpleNamespace(
        file_path="/app/uploads/personal/missing.md",
        original_filename="missing.md",
        processing_status="COMPLETED",
    )

    with pytest.raises(
        DocumentFileUnavailable,
        match="stored document file is unavailable",
    ):
        ingestion.reprocess(object(), document)
