"""Native LangChain tool-calling orchestration for interview and personal chat."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.observability import audit_event
from app.core.entity_registry import InterviewSession
from app.company_corpus.constants import SAMSUNG_COMPANY_NAME
from app.company_corpus.repositories.company_repository import CompanyRepository
from app.interview.repositories.interview_repository import InterviewRepository
from app.interview.services.memory import build_memory_context
from app.interview.services.tools import (
    InterviewToolContext,
    make_interview_tools,
)
from app.interview.dto.models import InterviewReportSummaryDTO, InterviewTurnResult
from app.shared.ai.runtime import (
    MAX_AGENT_ATTEMPTS,
    ToolCallingUnavailable,
    ToolCallAuditContext,
    ToolProtocolError,
    append_tool_messages,
    contains_internal_metadata,
    failure_metadata,
    model as _model,
    safe_source_title,
)
from app.shared.ai.budget import RetrievalBudget

def _scoped_interview_session(
    db: Session,
    session_id: int,
    user_id: int,
    company_id: int,
) -> InterviewSession:
    """Resolve only the current user's fixed Samsung interview session."""
    try:
        samsung = CompanyRepository(db).by_name(SAMSUNG_COMPANY_NAME)
        if samsung is None:
            raise LookupError("fixed company corpus is unavailable")
        samsung_id = int(samsung.id)
    except Exception as exc:
        raise ToolCallingUnavailable() from exc
    if int(company_id) != samsung_id:
        raise ToolCallingUnavailable()
    session = InterviewRepository(db).session(session_id, user_id, samsung_id)
    if session is None:
        raise ToolCallingUnavailable()
    return session


def _valid_result(content: Any) -> InterviewTurnResult:
    try:
        result = InterviewTurnResult.model_validate(content)
    except ValidationError as exc:
        raise ToolProtocolError("invalid interview json") from exc
    # Evidence citations are server-owned. Never preserve model-supplied
    # entries; only actual request-scoped tool hits may populate this field.
    result.evidence_sources = []
    if not result.interviewer_reply.strip() or contains_internal_metadata(result.interviewer_reply):
        raise ToolProtocolError("invalid interviewer reply")
    if result.evaluation is not None:
        if any(not 0 <= float(score) <= 100 for score in result.evaluation.scores.values()):
            raise ToolProtocolError("invalid evaluation score")
        for field in ("strengths", "weaknesses", "missing_points"):
            values = getattr(result.evaluation, field)
            if any(not isinstance(value, str) or contains_internal_metadata(value) for value in values):
                raise ToolProtocolError("invalid evaluation text")
        for field in ("improvement_advice", "improved_answer", "follow_up_question"):
            value = getattr(result.evaluation, field)
            if not isinstance(value, str) or contains_internal_metadata(value):
                raise ToolProtocolError("invalid evaluation text")
    result.fallback_used = False
    return result


def run_interview_turn(
    content: str, history: list[Any], target_role: str = "BACKEND",
    interview_type: str = "COMPREHENSIVE", difficulty: str = "INTERMEDIATE",
    phase: str = "INTERVIEW", icebreaker_count: int = 0, *, db: Session | None = None,
    user_id: int | None = None, company_id: int | None = None, session_id: int | None = None,
) -> InterviewTurnResult:
    """Run a full tool protocol. Old evidence arguments are deliberately ignored."""
    if db is None or user_id is None or company_id is None or session_id is None:
        raise ToolCallingUnavailable()
    # Never trust role/company values supplied by the model or a stale caller;
    # the persisted, fixed-Samsung session is the source of truth.
    system = SystemMessage(content=(
        "You are a Korean mock interviewer. Decide intent, phase, and whether to evaluate. "
        "Call search_company_evidence before stating Samsung, role, job, or other company-specific facts; use personal evidence and history when useful. "
        "For greetings and general conversation, you may answer without a tool. If company evidence is empty, do not call that tool again in this turn; say the company-specific basis is insufficient and continue naturally without inventing facts. "
        "Never expose URLs, document IDs, paths, filenames, or source metadata. Never end the session from text. "
        f"The persisted conversation is currently in {phase}; the prior icebreaker count is {icebreaker_count}. "
        'The final JSON contract is {"intent":"ANSWER|CLARIFICATION|CANDIDATE_QUESTION|OTHER",'
        '"interviewer_reply":"string","next_phase":"ICEBREAKER|INTERVIEW",'
        '"evaluation":null|{"scores":{"criterion":0-100},"strengths":["string"],'
        '"weaknesses":["string"],"missing_points":["string"],'
        '"improvement_advice":"string","improved_answer":"string",'
        '"follow_up_question":"string"}}.'
    ))
    for attempt in range(1, MAX_AGENT_ATTEMPTS + 1):
        try:
            # Scope lookup, budget and tool construction are part of the attempt:
            # failures here must be observable and receive the same retry policy.
            session = _scoped_interview_session(db, session_id, user_id, company_id)
            request_budget = RetrievalBudget()
            context = InterviewToolContext(
                db, user_id, session.company_id, session.id, session.target_role,
                budget=request_budget,
            )
            tool_list = make_interview_tools(context)
            tool_map = {item.name: item for item in tool_list}
            memory = build_memory_context(db, session.id, content, user_id=user_id)
            # llama-server's OpenAI-compatible endpoint accepts a single
            # leading system message only. Keep deterministic memory in that
            # same message so both native tool calling and structured-output
            # invocations preserve the full interview context.
            messages: list[Any] = [
                SystemMessage(content=f"{system.content}\n\n{memory.system_content()}"),
                HumanMessage(content=content),
            ]
            base_model = _model()
            model = base_model.bind_tools(tool_list)
            for _step in range(8):
                response = model.invoke(messages)
                calls = getattr(response, "tool_calls", None) or []
                if calls:
                    messages.append(response)
                    append_tool_messages(
                        response,
                        tool_map,
                        messages,
                        audit_context=ToolCallAuditContext(user_id=user_id, session_id=session_id),
                    )
                    if context.company_evidence_terminal:
                        model = base_model.bind_tools([
                            item
                            for item in tool_list
                            if item.name != "search_company_evidence"
                        ])
                    continue
                structured = base_model.with_structured_output(
                    InterviewTurnResult,
                    method="json_schema",
                )
                result = _valid_result(structured.invoke(messages))
                seen: set[tuple[str, int]] = set()
                for category, items in (("PERSONAL", context.personal_sources), ("COMPANY", context.company_sources)):
                    for item in items:
                        role = item.chunk.metadata_json.get("role_code")
                        source_category = category if category == "PERSONAL" else ("COMPANY_COMMON" if role == "COMMON" else "COMPANY_ROLE")
                        key = (source_category, item.document.id)
                        if key not in seen:
                            seen.add(key)
                            result.evidence_sources.append({"category": source_category, "title": safe_source_title(item.document.title)})
                return result
            raise ToolProtocolError("tool-call loop exceeded limit")
        except Exception as exc:
            stage, reason_code = failure_metadata(exc)
            audit_event(
                "llm.tool_call_failed",
                attempt=attempt,
                stage=stage,
                reason_code=reason_code,
                error_type=type(exc).__name__,
                session_id=session_id,
                user_id=user_id,
            )
            # Every retry receives a fresh request context, message chain, and model.
            continue
    raise ToolCallingUnavailable()

def run_interview_report(
    db: Session,
    session_id: int,
    target_role: str,
    interview_type: str,
    difficulty: str,
    *,
    user_id: int | None = None,
    company_id: int | None = None,
) -> str:
    # Reports must be scoped by the authenticated user and fixed Samsung
    # company too; deriving either from an unscoped session id is unsafe.
    if user_id is None or company_id is None:
        raise ToolCallingUnavailable()
    system = SystemMessage(
        content=(
            "You are a Korean interview coach. You MUST call "
            "read_interview_history before finalizing. Do not expose internal metadata. "
            'The final JSON contract is {"summary":"string"}.'
        )
    )
    for attempt in range(1, MAX_AGENT_ATTEMPTS + 1):
        try:
            session = _scoped_interview_session(db, session_id, user_id, company_id)
            # A report uses fresh scoped tools on each retry, just like a turn.
            context = InterviewToolContext(db, session.user_id, session.company_id, session.id, session.target_role, budget=RetrievalBudget())
            tools = make_interview_tools(context)
            history_tool = next(item for item in tools if item.name == "read_interview_history")
            messages: list[Any] = [system, HumanMessage(content="Generate the completed interview report.")]
            base_model = _model()
            model = base_model.bind_tools([history_tool])
            history_called = False
            for _step in range(5):
                response = model.invoke(messages)
                calls = getattr(response, "tool_calls", None) or []
                if calls:
                    messages.append(response)
                    if append_tool_messages(
                        response,
                        {history_tool.name: history_tool},
                        messages,
                        audit_context=ToolCallAuditContext(user_id=user_id, session_id=session_id),
                    ):
                        history_called = True
                    continue
                if not history_called:
                    raise ToolProtocolError("invalid report response")
                structured = base_model.with_structured_output(
                    InterviewReportSummaryDTO,
                    method="json_schema",
                )
                try:
                    report = InterviewReportSummaryDTO.model_validate(
                        structured.invoke(messages)
                    )
                except ValidationError as exc:
                    raise ToolProtocolError("invalid report json") from exc
                summary = report.summary
                if contains_internal_metadata(summary):
                    raise ToolProtocolError("invalid report json")
                return summary.strip()
        except Exception as exc:
            stage, reason_code = failure_metadata(exc)
            audit_event(
                "llm.tool_call_failed",
                attempt=attempt,
                stage=f"report_{stage}",
                reason_code=reason_code,
                error_type=type(exc).__name__,
                session_id=session_id,
                user_id=user_id,
            )
            continue
    raise ToolCallingUnavailable()
