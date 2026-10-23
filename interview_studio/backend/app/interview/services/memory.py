"""Deterministic, session-scoped three-tier memory for the interview agent."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.observability import audit_event
from app.interview.dto.models import InterviewMemorySummaryDTO
from app.interview.entities.models import InterviewMessage, InterviewSession
from app.interview.repositories.interview_repository import InterviewRepository
from app.shared.ai.runtime import clean_text, contains_internal_metadata, model as _model
from app.shared.clients.embedding import embed_query, embedding


SHORT_MEMORY_LIMIT = 20
MID_MEMORY_LIMIT = 4
LONG_MEMORY_LIMIT = 3
_MESSAGE_LIMIT = 700
_SUMMARY_LIMIT = 1_600


@dataclass(frozen=True)
class InterviewMemoryContext:
    short: list[str]
    mid: list[str]
    long: list[str]

    def system_content(self) -> str:
        def section(name: str, values: list[str]) -> str:
            body = "\n".join(f"- {value}" for value in values) or "- 없음"
            return f"[{name}]\n{body}"

        return (
            "The following is server-provided session memory. Use it only to keep "
            "the interview coherent; do not mention memory, identifiers, or hidden context.\n"
            + section("SHORT_MEMORY", self.short)
            + "\n"
            + section("RECENT_MID_MEMORY", self.mid)
            + "\n"
            + section("RELEVANT_OLDER_MEMORY", self.long)
        )


def _safe_message(message: InterviewMessage) -> str:
    speaker = "지원자" if message.speaker == "CANDIDATE" else "면접관"
    content = clean_text(message.content, _MESSAGE_LIMIT)
    return f"{speaker}: {content}" if content else ""


def _safe_summary(value: str) -> str:
    text = clean_text(value, _SUMMARY_LIMIT)
    return text if text and not contains_internal_metadata(text) else ""


def _summary_text(payload: InterviewMemorySummaryDTO) -> str:
    sections = (
        ("지원자 경험·주장", payload.candidate_experiences_and_claims),
        ("강점", payload.strengths),
        ("보완점", payload.gaps),
        ("미해결 후속 주제", payload.unresolved_follow_ups),
    )
    values: list[str] = []
    for label, items in sections:
        cleaned = [clean_text(str(item), 300) for item in items]
        cleaned = [item for item in cleaned if item and not contains_internal_metadata(item)]
        if cleaned:
            values.append(f"{label}: " + "; ".join(cleaned[:6]))
    text = _safe_summary("\n".join(values))
    if not text:
        raise ValueError("empty memory summary")
    return text


def _summary_prompt(messages: Iterable[InterviewMessage]) -> str:
    transcript = "\n".join(value for value in (_safe_message(item) for item in messages) if value)
    return (
        "Summarize this Korean mock-interview block compactly. Preserve only candidate "
        "experiences/claims, demonstrated strengths, gaps, and unresolved follow-ups. "
        "Do not include document names, URLs, paths, identifiers, source references, or invented facts.\n\n"
        + transcript
    )


def summarize_block(messages: list[InterviewMessage]) -> str:
    """Use schema constrained output so saved memory remains compact and untrusted-safe."""
    structured = _model().with_structured_output(InterviewMemorySummaryDTO, method="json_schema")
    try:
        payload = InterviewMemorySummaryDTO.model_validate(
            structured.invoke(
                [
                    SystemMessage(content="Return only the requested structured interview-memory summary."),
                    HumanMessage(content=_summary_prompt(messages)),
                ]
            )
        )
    except ValidationError as exc:
        raise ValueError("invalid memory summary") from exc
    return _summary_text(payload)


def persist_due_summaries(db: Session, session: InterviewSession, user_id: int) -> None:
    """Best-effort post-commit work. A failure never rolls back interview messages."""
    repository = InterviewRepository(db)
    for start, end, messages in repository.completed_memory_blocks(session.id):
        if repository.memory_summary(session.id, end) is not None:
            continue
        try:
            summary = summarize_block(messages)
            vector = embedding(summary)
            if repository.memory_summary(session.id, end) is not None:
                continue
            repository.add_memory_summary(
                interview_session_id=session.id,
                start_sequence_number=start,
                end_sequence_number=end,
                summary=summary,
                embedding=vector,
            )
            db.commit()
        except IntegrityError:
            # Another request completed this exact unique block first.
            db.rollback()
            if repository.memory_summary(session.id, end) is None:
                audit_event(
                    "interview.memory_summary_failed",
                    attempt=1,
                    stage="persist",
                    error_type="IntegrityError",
                    session_id=session.id,
                    user_id=user_id,
                )
        except Exception as exc:
            db.rollback()
            audit_event(
                "interview.memory_summary_failed",
                attempt=1,
                stage="summary_or_embedding",
                error_type=type(exc).__name__,
                session_id=session.id,
                user_id=user_id,
            )


def build_memory_context(
    db: Session,
    session_id: int,
    candidate_content: str,
    *,
    user_id: int | None = None,
) -> InterviewMemoryContext:
    """Prepare bounded direct short/mid memory plus vector-retrieved older memory."""
    repository = InterviewRepository(db)
    # Direct memory is valuable even when the embedding provider is unavailable.
    # Keep this read/formatting path isolated from the optional long-memory lookup.
    try:
        short_rows = repository.recent_messages(session_id, SHORT_MEMORY_LIMIT)
        short = [item for item in (_safe_message(row) for row in short_rows) if item]
        latest = repository.latest_memory_summaries(session_id, MID_MEMORY_LIMIT)
        mid = [item for item in (_safe_summary(row.summary) for row in latest) if item]
    except Exception as exc:
        audit_event(
            "interview.memory_context_failed",
            attempt=1,
            stage="direct_memory",
            error_type=type(exc).__name__,
            session_id=session_id,
            user_id=user_id,
        )
        return InterviewMemoryContext(short=[], mid=[], long=[])

    try:
        long: list[str] = []
        query = clean_text(
            candidate_content + "\n" + "\n".join(short),
            SHORT_MEMORY_LIMIT * 180,
        )
        if query:
            excluded = {row.end_sequence_number for row in latest}
            try:
                older = repository.older_similar_memory_summaries(
                    session_id,
                    embed_query(query),
                    excluded,
                    LONG_MEMORY_LIMIT,
                )
            except Exception as exc:
                audit_event(
                    "rag.retrieval_failed",
                    scope="INTERVIEW_LONG_MEMORY",
                    purpose="interview_long_memory",
                    error_type=type(exc).__name__,
                    session_id=session_id,
                    user_id=user_id,
                )
                raise
            long = [item for item in (_safe_summary(row.summary) for row in older) if item]
            audit_event(
                "rag.retrieval_completed",
                scope="INTERVIEW_LONG_MEMORY",
                purpose="interview_long_memory",
                result_count=len(long),
                results=[
                    {
                        "source": "이전 면접 요약",
                        "category": "INTERVIEW_MEMORY",
                        "preview": clean_text(item, 300),
                    }
                    for item in long
                ],
                session_id=session_id,
                user_id=user_id,
            )
        return InterviewMemoryContext(short=short, mid=mid, long=long)
    except Exception as exc:
        # Long memory is optional retrieval enhancement. An embedding/vector outage
        # must not discard the deterministic current-session context.
        audit_event(
            "interview.memory_context_failed",
            attempt=1,
            stage="long_memory",
            error_type=type(exc).__name__,
            session_id=session_id,
            user_id=user_id,
        )
        return InterviewMemoryContext(short=short, mid=mid, long=[])
