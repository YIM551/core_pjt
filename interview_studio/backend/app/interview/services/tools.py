"""Request-scoped, read-only tools for CareerFit interview agents."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from langchain_core.tools import tool
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.document.services.retrieval import (
    EvidenceHit,
    audit_retrieval_delivered,
    search_company_evidence as retrieve_company,
    search_personal_evidence as retrieve_personal,
    safe_evidence_entry,
    safe_evidence_payload,
)
from app.interview.repositories.interview_repository import InterviewRepository
from app.shared.ai.budget import RetrievalBudget
from app.shared.ai.runtime import (
    ToolProtocolError,
    clean_text,
)


def _clean_history_values(values: object, limit: int = 240) -> list[str]:
    """Normalize evaluation lists before they are handed to the model."""
    if not isinstance(values, (list, tuple)):
        return []
    cleaned: list[str] = []
    for value in values:
        text = clean_text(str(value), limit)
        if text:
            cleaned.append(text)
    return cleaned


@dataclass
class InterviewToolContext:
    db: Session
    user_id: int
    company_id: int
    session_id: int
    target_role: str
    budget: RetrievalBudget = field(default_factory=RetrievalBudget)
    personal_sources: list[EvidenceHit] = field(default_factory=list)
    company_sources: list[EvidenceHit] = field(default_factory=list)
    _company_terminal_result: str | None = None

    @property
    def company_evidence_terminal(self) -> bool:
        return self._company_terminal_result is not None

    def _reserve_call(self) -> bool:
        settings = get_settings()
        if (
            self.budget.used_tool_calls >= settings.retrieval_request_max_tool_calls
            or len(self.budget.seen_chunks) >= settings.retrieval_request_max_chunks
            or self.budget.used_chars >= settings.retrieval_request_char_budget
        ):
            return False
        self.budget.used_tool_calls += 1
        return True

    def _consume(self, hits: list[EvidenceHit]) -> tuple[list[EvidenceHit], str | None]:
        settings = get_settings()
        accepted: list[EvidenceHit] = []
        for hit in hits:
            if hit.chunk.id in self.budget.seen_chunks:
                continue
            content_chars = len(clean_text(hit.chunk.content))
            if len(self.budget.seen_chunks) >= settings.retrieval_request_max_chunks:
                break
            if self.budget.used_chars + content_chars > settings.retrieval_request_char_budget:
                break
            self.budget.seen_chunks.add(hit.chunk.id)
            self.budget.used_chars += content_chars
            accepted.append(hit)
        return accepted, None if accepted else "no_relevant_evidence"

    def search_personal(self, query: str) -> str:
        if not self._reserve_call():
            return json.dumps(
                {"evidence": [], "reason": "retrieval_budget_exhausted"},
                ensure_ascii=False,
            )
        personal, reason = self._consume(
            retrieve_personal(
                self.db,
                query,
                user_id=self.user_id,
                session_id=self.session_id,
                purpose="interview_personal_evidence",
            )
        )
        delivered = [item for item in personal if safe_evidence_entry(item) is not None]
        payload = safe_evidence_payload(delivered)
        self.personal_sources.extend(delivered)
        audit_retrieval_delivered(
            scope="PERSONAL",
            purpose="interview_personal_evidence",
            hits=delivered,
            payload=payload,
            user_id=self.user_id,
            session_id=self.session_id,
        )
        return json.dumps(
            {"evidence": payload, "reason": reason if payload else "no_relevant_evidence"},
            ensure_ascii=False,
        )

    def search_company(self, query: str) -> str:
        if self._company_terminal_result is not None:
            return self._company_terminal_result
        if not self._reserve_call():
            raise ToolProtocolError("retrieval_budget_exhausted")
        company, reason = self._consume(
            retrieve_company(
                self.db,
                query,
                company_id=self.company_id,
                target_role=self.target_role,
                user_id=self.user_id,
                session_id=self.session_id,
                purpose="interview_company_evidence",
            )
        )
        delivered = [item for item in company if safe_evidence_entry(item) is not None]
        payload = safe_evidence_payload(delivered)
        self.company_sources.extend(delivered)
        audit_retrieval_delivered(
            scope="COMPANY",
            purpose="interview_company_evidence",
            hits=delivered,
            payload=payload,
            company_id=self.company_id,
            target_role=self.target_role,
            user_id=self.user_id,
            session_id=self.session_id,
        )
        result = json.dumps(
            {"evidence": payload, "reason": reason if payload else "no_relevant_evidence"},
            ensure_ascii=False,
        )
        if not payload:
            self._company_terminal_result = result
        return result

    def history(self) -> str:
        repository = InterviewRepository(self.db)
        rows = repository.recent_messages(self.session_id)
        messages = [
            {"speaker": row.speaker, "content": clean_text(row.content, 500)}
            for row in rows
            if clean_text(row.content, 500)
        ]
        evaluations = repository.evaluations(self.session_id)
        return json.dumps(
            {
                "messages": messages,
                "evaluations": [
                    {
                        "score": item.total_score,
                        "strengths": _clean_history_values(item.strengths),
                        "weaknesses": _clean_history_values(item.weaknesses),
                        "missing_points": _clean_history_values(item.missing_points),
                        "improvement_advice": clean_text(
                            str(item.improvement_advice or ""), 500
                        ),
                        "improved_answer": clean_text(
                            str(item.improved_answer or ""), 500
                        ),
                        "follow_up_question": clean_text(
                            str(item.follow_up_question or ""), 300
                        ),
                    }
                    for item in evaluations
                ],
            },
            ensure_ascii=False,
        )


def make_interview_tools(context: InterviewToolContext):
    """Create closures so model arguments can never select tenant/session scope."""

    @tool
    def search_personal_evidence(query: str) -> str:
        """Search only the authenticated candidate's personal uploaded evidence."""
        return context.search_personal(query)

    @tool
    def search_company_evidence(query: str) -> str:
        """Search the fixed Samsung common and target-role interview corpus."""
        return context.search_company(query)

    @tool
    def read_interview_history() -> str:
        """Read recent messages from the current interview session only."""
        return context.history()

    return [
        search_personal_evidence,
        search_company_evidence,
        read_interview_history,
    ]
