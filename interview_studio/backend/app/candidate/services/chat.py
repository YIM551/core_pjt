"""Candidate-domain personal RAG chat, backed by native tool calling."""
from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from sqlalchemy.orm import Session

from app.candidate.dto.chat import ChatRequest
from app.auth.entities.models import User
from app.core.config import get_settings
from app.core.observability import audit_event
from app.document.services.retrieval import (
    audit_retrieval_delivered,
    safe_evidence_entry,
    safe_evidence_payload,
    search_personal_evidence,
)
from app.shared.ai.budget import RetrievalBudget
from app.shared.ai.runtime import (
    MAX_AGENT_ATTEMPTS,
    ToolCallingUnavailable,
    ToolCallAuditContext,
    ToolProtocolError,
    append_tool_messages,
    clean_text,
    contains_internal_metadata,
    failure_metadata,
    model,
    safe_source_title,
)


class _PersonalToolContext:
    """Server-injected candidate scope; the model never supplies a user id."""
    def __init__(self, db: Session, user_id: int, budget: RetrievalBudget) -> None:
        self.db, self.user_id, self.budget = db, user_id, budget
        self.sources = []

    def search(self, query: str) -> str:
        settings = get_settings()
        if self.budget.used_tool_calls >= settings.retrieval_request_max_tool_calls:
            return json.dumps({"evidence": [], "reason": "retrieval_budget_exhausted"}, ensure_ascii=False)
        self.budget.used_tool_calls += 1
        accepted = []
        for hit in search_personal_evidence(
            self.db,
            query,
            user_id=self.user_id,
            purpose="candidate_chat_personal_evidence",
        ):
            if hit.chunk.id in self.budget.seen_chunks:
                continue
            content = clean_text(hit.chunk.content)
            if not content or len(self.budget.seen_chunks) >= settings.retrieval_request_max_chunks:
                continue
            if self.budget.used_chars + len(content) > settings.retrieval_request_char_budget:
                break
            self.budget.seen_chunks.add(hit.chunk.id)
            self.budget.used_chars += len(content)
            accepted.append(hit)
        delivered = [item for item in accepted if safe_evidence_entry(item) is not None]
        self.sources.extend(delivered)
        evidence = safe_evidence_payload(delivered)
        audit_retrieval_delivered(
            scope="PERSONAL",
            purpose="candidate_chat_personal_evidence",
            hits=delivered,
            payload=evidence,
            user_id=self.user_id,
        )
        return json.dumps({"evidence": evidence, "reason": None if evidence else "no_relevant_evidence"}, ensure_ascii=False)


class CandidateChatService:
    """Candidate-domain entry point for personal RAG conversation."""

    def __init__(self, db: Session):
        self.db = db

    def answer(self, user: User, payload: ChatRequest) -> dict[str, object]:
        system = SystemMessage(content=(
            "You are a Korean career assistant. Call search_personal_evidence before stating user-specific facts. "
            "Never expose URLs, document IDs, paths, filenames, or source metadata. Return plain Korean text."
        ))
        for attempt in range(1, MAX_AGENT_ATTEMPTS + 1):
            try:
                # Context, tool closure and budget are re-created for every attempt.
                context = _PersonalToolContext(self.db, user.id, RetrievalBudget())

                @tool("search_personal_evidence")
                def search_personal_evidence_tool(query: str) -> str:
                    """Search only the authenticated candidate's uploaded personal evidence."""
                    return context.search(query)

                messages = [system, HumanMessage(content=payload.question)]
                tool_map = {search_personal_evidence_tool.name: search_personal_evidence_tool}
                bound_model = model().bind_tools([search_personal_evidence_tool])
                used_evidence = False
                for _step in range(6):
                    response = bound_model.invoke(messages)
                    if getattr(response, "tool_calls", None):
                        messages.append(response)
                        used_evidence = used_evidence or bool(
                            append_tool_messages(
                                response,
                                tool_map,
                                messages,
                                audit_context=ToolCallAuditContext(user_id=user.id),
                            )
                        )
                        continue
                    answer = getattr(response, "content", None)
                    if not isinstance(answer, str) or not answer.strip() or contains_internal_metadata(answer):
                        raise ToolProtocolError("invalid personal chat response")
                    sources = ([{"category": "PERSONAL", "title": safe_source_title(hit.document.title)} for hit in context.sources] if used_evidence else [])
                    return {"answer": answer.strip(), "sources": sources}
                raise ToolProtocolError("tool-call loop exceeded limit")
            except Exception as exc:
                stage, reason_code = failure_metadata(exc)
                audit_event(
                    "llm.tool_call_failed",
                    attempt=attempt,
                    stage=f"candidate_{stage}",
                    reason_code=reason_code,
                    error_type=type(exc).__name__,
                    user_id=user.id,
                )
        raise ToolCallingUnavailable()
