from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.entity_registry import Document, DocumentChunk
from app.core.observability import audit_event
from app.shared.clients.embedding import embed_query, embedding_metadata
from app.shared.ai.runtime import clean_text, contains_internal_metadata, safe_source_title
from app.document.repositories.document_repository import DocumentRepository


@dataclass(frozen=True)
class EvidenceHit:
    scope: Literal["PERSONAL", "COMPANY"]
    chunk: DocumentChunk
    document: Document
    distance: float

    def tool_payload(self) -> dict:
        return {
            "scope": self.scope,
            "document_id": self.document.id,
            "title": self.document.title,
            "chunk_id": self.chunk.id,
            "chunk_index": self.chunk.chunk_index,
            "content": self.chunk.content,
            "distance": self.distance,
            "role_code": self.chunk.metadata_json.get("role_code"),
        }


def safe_evidence_entry(item: EvidenceHit) -> dict[str, str] | None:
    content = clean_text(item.chunk.content)
    if not content or contains_internal_metadata(content):
        return None
    category = clean_text(str(item.chunk.metadata_json.get("role_code") or item.scope), 80)
    if not category or contains_internal_metadata(category):
        category = item.scope
    return {"category": category, "content": content}


def safe_evidence_payload(items: list[EvidenceHit]) -> list[dict[str, str]]:
    """Return only evidence fields that are safe to pass to an LLM."""
    return [entry for item in items if (entry := safe_evidence_entry(item)) is not None]


def audit_retrieval_delivered(
    *,
    scope: str,
    purpose: str,
    hits: list[EvidenceHit],
    payload: list[dict[str, str]],
    **fields: object,
) -> None:
    """Log the sanitized evidence actually supplied after budget filtering."""
    details: list[dict[str, object]] = []
    for hit in hits:
        entry = safe_evidence_entry(hit)
        if entry is None:
            continue
        content = entry.get("content", "")
        if not content:
            continue
        distance = float(hit.distance)
        detail: dict[str, object] = {
            "source": safe_source_title(hit.document.title),
            "category": entry.get("category", scope),
            "preview": clean_text(content, 300),
        }
        if distance == distance and abs(distance) != float("inf"):
            detail["distance"] = round(distance, 4)
        details.append(detail)
    audit_event(
        "rag.retrieval_completed",
        scope=scope,
        purpose=purpose,
        result_count=len(details),
        results=details,
        **fields,
    )

@dataclass
class _SelectionState:
    per_document: dict[int, list[int]] = field(default_factory=dict)
    used_chars: int = 0

def _select_hits(rows, scope: Literal["PERSONAL", "COMPANY"], threshold: float | None,
                 top_k: int, char_budget: int,
                 state: _SelectionState | None = None) -> list[EvidenceHit]:
    settings = get_settings()
    state = state or _SelectionState()
    result: list[EvidenceHit] = []
    for chunk, document, distance in rows:
        distance = float(distance)
        if threshold is not None and distance > threshold:
            continue
        indexes = state.per_document.setdefault(document.id, [])
        if len(indexes) >= settings.retrieval_per_document_limit:
            continue
        # Overlapping adjacent chunks mostly repeat the same source text.
        if any(abs(chunk.chunk_index - existing) <= 1 for existing in indexes):
            continue
        if state.used_chars + len(chunk.content) > char_budget:
            continue
        result.append(EvidenceHit(scope, chunk, document, distance))
        indexes.append(chunk.chunk_index)
        state.used_chars += len(chunk.content)
        if len(result) >= top_k:
            break
    return result


def search_personal_evidence(
    db: Session,
    query: str,
    *,
    user_id: int,
    top_k: int = 6,
    session_id: int | None = None,
    purpose: str = "personal_rag",
) -> list[EvidenceHit]:
    fields: dict[str, object] = {"scope": "PERSONAL", "purpose": purpose, "user_id": user_id}
    if session_id is not None:
        fields["session_id"] = session_id
    try:
        settings = get_settings()
        vector = embed_query(query)
        rows = DocumentRepository(db).vector_rows("PERSONAL", vector, user_id=user_id)
        hits = _select_hits(
            rows, "PERSONAL",
            None,
            min(top_k, settings.retrieval_top_k, 6),
            settings.retrieval_context_char_budget,
        )
    except Exception as exc:
        audit_event("rag.retrieval_failed", **fields, error_type=type(exc).__name__)
        raise
    return hits


def search_company_evidence(
    db: Session,
    query: str,
    *,
    company_id: int,
    target_role: str,
    top_k: int = 3,
    user_id: int | None = None,
    session_id: int | None = None,
    purpose: str = "company_rag",
) -> list[EvidenceHit]:
    fields: dict[str, object] = {
        "scope": "COMPANY", "purpose": purpose, "company_id": company_id, "target_role": target_role,
    }
    if user_id is not None:
        fields["user_id"] = user_id
    if session_id is not None:
        fields["session_id"] = session_id
    try:
        settings = get_settings()
        vector = embed_query(query)
        repo = DocumentRepository(db)
        role_rows = repo.vector_rows("COMPANY", vector, company_id=company_id, role_code=target_role)
        common_rows = repo.vector_rows("COMPANY", vector, company_id=company_id, role_code="COMMON")
        limit = min(top_k, settings.retrieval_top_k, 3)
        selection = _SelectionState()
        role_hits = _select_hits(
            role_rows, "COMPANY",
            settings.company_retrieval_max_cosine_distance,
            limit, settings.retrieval_context_char_budget, selection,
        )
        remaining = max(0, limit - len(role_hits))
        common_hits = _select_hits(
            common_rows, "COMPANY",
            settings.company_retrieval_max_cosine_distance,
            remaining, settings.retrieval_context_char_budget, selection,
        ) if remaining else []
        hits = role_hits + common_hits
    except Exception as exc:
        audit_event("rag.retrieval_failed", **fields, error_type=type(exc).__name__)
        raise
    return hits
