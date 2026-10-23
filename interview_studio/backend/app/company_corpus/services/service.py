from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.entity_registry import Company, Document, DocumentChunk
from app.company_corpus.constants import ROLE_CODES, SAMSUNG_COMPANY_NAME
from app.shared.clients.embedding import embed_documents, embedding, embedding_metadata
from app.document.services.ingestion import chunks
from app.company_corpus.repositories.company_repository import CompanyRepository


SUPPORTED_SUFFIXES = {".md", ".txt"}
_DEFAULT_EMBEDDING = embedding


@dataclass(frozen=True)
class CorpusSource:
    path: Path
    relative_path: str
    role_code: str
    text: str


def load_sources(root: Path) -> list[CorpusSource]:
    resolved_root = root.resolve()
    role_directories = [("COMMON", resolved_root / "common")]
    role_directories.extend(
        (role, resolved_root / role) for role in ROLE_CODES
    )
    sources: list[CorpusSource] = []
    for role_code, directory in role_directories:
        if not directory.is_dir():
            continue
        for path in sorted(item for item in directory.iterdir() if item.is_file()):
            if path.suffix.lower() not in SUPPORTED_SUFFIXES:
                continue
            # Source links are retained in version-controlled files but are not model
            # evidence: they would otherwise leak through retrieved chunks.
            text = path.read_text(encoding="utf-8").split("## 원문 출처", 1)[0].strip()
            if not text:
                continue
            sources.append(
                CorpusSource(
                    path=path,
                    relative_path=path.relative_to(resolved_root).as_posix(),
                    role_code=role_code,
                    text=text,
                )
            )
    return sources


def _corpus_vectors(parts: list[str]) -> list[list[float]]:
    # Preserve the existing deterministic test seam; production uses batching.
    if embedding is not _DEFAULT_EMBEDDING:
        return [embedding(part) for part in parts]
    return embed_documents(parts)


def replace_samsung_corpus(db: Session, root: Path) -> tuple[int, int]:
    sources = load_sources(root)
    if not sources:
        raise ValueError(
            f"No non-empty .md or .txt files found under {root.resolve()}"
        )

    source_parts = [(source, list(chunks(source.text))) for source in sources]
    flat_parts = [part for _, parts in source_parts for part in parts]
    flat_vectors = iter(_corpus_vectors(flat_parts))
    prepared = [
        (
            source,
            [
                (index, content, next(flat_vectors))
                for index, content in enumerate(parts)
            ],
        )
        for source, parts in source_parts
    ]

    company = CompanyRepository(db).get_or_create_active(SAMSUNG_COMPANY_NAME)

    repository = CompanyRepository(db)
    chunk_count = repository.replace_corpus_documents(company.id, prepared)
    return len(prepared), chunk_count
