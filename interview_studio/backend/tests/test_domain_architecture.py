from pathlib import Path


ROOT = Path(__file__).parents[1] / "app"


def test_domain_first_tree_and_legacy_python_modules_are_absent():
    for domain in ("auth", "candidate", "document", "interview", "company_corpus", "audit"):
        assert (ROOT / domain).is_dir()
    assert not (ROOT / "domains").joinpath("auth").exists()
    for legacy in ("api", "controllers", "dto", "entities", "repositories", "services", "clients", "utils", "models.py", "schemas.py"):
        assert not any((ROOT / legacy).rglob("*.py")) if (ROOT / legacy).is_dir() else not (ROOT / legacy).exists()


def test_controllers_do_not_import_sqlalchemy_or_clients_directly():
    for domain in ("auth", "candidate", "document", "interview"):
        for controller in (ROOT / domain / "controllers").glob("*.py"):
            if controller.name == "__init__.py":
                continue
            text = controller.read_text(encoding="utf-8")
            assert "sqlalchemy import" not in text
            assert "shared.clients" not in text
            assert ".repositories" not in text


def test_candidate_and_document_services_are_transport_independent():
    service_roots = (
        ROOT / "candidate" / "services",
        ROOT / "document" / "services",
    )
    for service_root in service_roots:
        for module in service_root.glob("*.py"):
            text = module.read_text(encoding="utf-8")
            assert "from fastapi" not in text
            assert "import fastapi" not in text


def test_document_http_dto_never_exposes_original_filename():
    from app.document.dto.models import DocumentResponse

    assert "original_filename" not in DocumentResponse.model_fields


def test_domain_exception_modules_are_transport_independent():
    for domain in ("document", "interview"):
        text = (ROOT / domain / "exceptions.py").read_text(encoding="utf-8")
        assert "fastapi" not in text
        assert "shared.http" not in text


def test_document_filesystem_calls_stay_in_shared_client():
    for module in (ROOT / "document" / "services").glob("*.py"):
        text = module.read_text(encoding="utf-8")
        assert ".write_bytes(" not in text
        assert ".read_bytes(" not in text
        assert ".unlink(" not in text
        assert ".mkdir(" not in text


def test_removed_candidate_profile_and_project_code_has_no_live_references():
    removed_names = (
        "CandidateProfile",
        "CandidateProject",
        "CandidateService",
        "CandidateRepository",
        "ProjectNotFound",
        "InvalidProjectDateRange",
    )
    for module in ROOT.rglob("*.py"):
        text = module.read_text(encoding="utf-8")
        for removed_name in removed_names:
            assert removed_name not in text, f"{removed_name} remains in {module}"
