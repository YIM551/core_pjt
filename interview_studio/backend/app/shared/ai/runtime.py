"""Protocol validation shared by the candidate and interview agents.

This module deliberately contains no domain imports.  It is the single place
where a model's native tool calls are accepted and converted into ToolMessage
objects.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from langchain_core.messages import ToolMessage

from app.shared.clients.llm import chat_model
from app.core.observability import audit_event

MAX_AGENT_ATTEMPTS = 3


class ToolProtocolError(RuntimeError):
    """Raised when the model does not follow the native tool-call contract."""


class ToolCallingUnavailable(RuntimeError):
    """The model failed to complete the native tool-calling protocol."""


@dataclass(frozen=True)
class ToolCallAuditContext:
    """Server-owned identifiers that may be attached to tool-call audit events."""

    user_id: int | None = None
    session_id: int | None = None


def failure_metadata(exc: Exception) -> tuple[str, str]:
    """Map known protocol failures to safe, stable audit fields only."""
    if isinstance(exc, ToolProtocolError):
        category = {
            "malformed tool call": ("tool_protocol", "malformed_tool_call"),
            "unknown or malformed tool call": ("tool_protocol", "malformed_tool_call"),
            "history tool takes no arguments": ("tool_protocol", "invalid_tool_args"),
            "tool arguments are invalid": ("tool_protocol", "invalid_tool_args"),
            "unsafe tool result": ("tool_result", "tool_result_unsafe"),
            "company evidence is unavailable": ("company_retrieval", "company_evidence_unavailable"),
            "no_relevant_evidence": ("company_retrieval", "company_evidence_unavailable"),
            "retrieval_budget_exhausted": ("company_retrieval", "company_evidence_unavailable"),
            "required company tool was not called": ("tool_protocol", "required_company_tool_missing"),
            "invalid interview json": ("final_response", "invalid_final_json"),
            "invalid report json": ("final_response", "invalid_final_json"),
            "invalid report response": ("final_response", "invalid_final_json"),
            "invalid personal chat response": ("final_response", "invalid_final_response"),
            "unsafe final response": ("final_response", "unsafe_final_response"),
            "invalid interviewer reply": ("final_response", "invalid_interviewer_reply"),
            "invalid evaluation score": ("final_response", "invalid_evaluation"),
            "invalid evaluation text": ("final_response", "invalid_evaluation"),
            "tool-call loop exceeded limit": ("tool_protocol", "loop_limit"),
        }.get(str(exc))
        return category or ("tool_protocol", "tool_protocol_error")
    if isinstance(exc, ToolCallingUnavailable):
        return "scope", "scoped_session_unavailable"
    return "model_invocation", "model_or_dependency_error"


_INTERNAL_METADATA = re.compile(
    r"(?:https?://[^\s]+|\bdoc_[A-Za-z0-9_-]+\b|[A-Za-z]:[\\/][^\s]+|"
    r"(?<![A-Za-z0-9])/(?:app|home|tmp|var|etc|usr|opt|mnt|workspace|uploads)(?:/[^\s]*)?|"
    r"\[.+?\]\(.+?\)|##\s*원문\s*출처)",
    re.IGNORECASE,
)


def contains_internal_metadata(value: str) -> bool:
    return bool(_INTERNAL_METADATA.search(value))


def clean_text(value: str, limit: int = 700) -> str:
    value = value.split("## 원문 출처", 1)[0]
    value = _INTERNAL_METADATA.sub("", value)
    return " ".join(value.split())[:limit].strip()


def safe_source_title(value: str) -> str:
    raw = str(value or "").strip()
    if not raw or contains_internal_metadata(raw) or "/" in raw or "\\" in raw or ".." in raw:
        return "회사 직무 자료"
    stem = Path(raw).stem
    return stem[:80] if stem and not contains_internal_metadata(stem) else "회사 직무 자료"


def model():
    return chat_model()


def sanitize_tool_result(value: str) -> str:
    try:
        payload = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return clean_text(value, 4000)

    def clean(item: Any) -> Any:
        if isinstance(item, str):
            return clean_text(item, 4000)
        if isinstance(item, list):
            return [clean(entry) for entry in item]
        if isinstance(item, dict):
            return {str(key): clean(entry) for key, entry in item.items()}
        return item

    return json.dumps(clean(payload), ensure_ascii=False)


def sanitize_evidence_tool_result(value: str) -> str:
    """Reduce a controlled retrieval response to its safe public evidence shape.

    Retrieval text is untrusted even after the retrieval service has selected it.
    Do this field-by-field rather than rejecting an otherwise useful tool call
    because one chunk happened to contain a source URL or a Markdown citation.
    This is intentionally *not* used for arbitrary tool output.
    """
    try:
        payload = json.loads(value)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ToolProtocolError("unsafe tool result") from exc
    if isinstance(payload, list):
        payload = {"evidence": payload, "reason": None}
    if not isinstance(payload, dict) or not isinstance(payload.get("evidence"), list):
        raise ToolProtocolError("unsafe tool result")

    evidence: list[dict[str, str]] = []
    for item in payload["evidence"]:
        if not isinstance(item, dict):
            continue
        content = clean_text(str(item.get("content") or ""), 4000)
        if not content or contains_internal_metadata(content):
            continue
        category = clean_text(str(item.get("category") or ""), 80)
        if not category or contains_internal_metadata(category):
            category = "PERSONAL"
        evidence.append({"category": category, "content": content})

    reason = payload.get("reason")
    safe_reason = reason if isinstance(reason, str) and reason in {
        "no_relevant_evidence", "retrieval_budget_exhausted"
    } else None
    if not evidence:
        safe_reason = "no_relevant_evidence"
    return json.dumps({"evidence": evidence, "reason": safe_reason}, ensure_ascii=False)


def append_tool_messages(
    response: Any,
    tools: dict[str, Any],
    messages: list[Any],
    *,
    audit_context: ToolCallAuditContext | None = None,
) -> list[str]:
    calls = getattr(response, "tool_calls", None) or []
    called: list[str] = []
    for call in calls:
        name = call.get("name") if isinstance(call, dict) else None
        tool_name = name if isinstance(name, str) and name in tools else "unknown"
        call_id = call.get("id") if isinstance(call, dict) else None
        fields: dict[str, object] = {"tool_name": tool_name}
        if isinstance(call_id, str) and call_id:
            fields["call_id"] = call_id[:128]
        if audit_context is not None:
            if audit_context.session_id is not None:
                fields["session_id"] = audit_context.session_id
            if audit_context.user_id is not None:
                fields["user_id"] = audit_context.user_id
        audit_event("llm.tool_call_started", **fields)
        try:
            if not isinstance(call, dict):
                raise ToolProtocolError("malformed tool call")
            args = call.get("args")
            if name not in tools or not isinstance(args, dict):
                raise ToolProtocolError("unknown or malformed tool call")
            if name == "read_interview_history":
                if args:
                    raise ToolProtocolError("history tool takes no arguments")
            elif set(args) != {"query"} or not isinstance(args["query"], str) or not args["query"].strip():
                raise ToolProtocolError("tool arguments are invalid")
            result = tools[name].invoke(args)
            if not isinstance(result, str):
                raise ToolProtocolError("unsafe tool result")
            # Only the two retrieval tools have this restricted evidence DTO.
            # Other tool output remains subject to generic strict validation.
            is_evidence_tool = name in {
                "search_personal_evidence",
                "search_company_evidence",
            }
            if is_evidence_tool:
                result = sanitize_evidence_tool_result(result)
            else:
                result = sanitize_tool_result(result)
            # Evidence payloads are validated field-by-field above.  Running the
            # generic whole-JSON detector here is both redundant and incorrect:
            # its Markdown pattern can start at the JSON evidence array's `[` and
            # end at a harmless `](` sequence inside retrieved code/text.
            # Keep the strict whole-result check for every other tool payload.
            if not is_evidence_tool and contains_internal_metadata(result):
                raise ToolProtocolError("unsafe tool result")
            messages.append(ToolMessage(content=result, tool_call_id=str(call.get("id", name))))
            called.append(name)
        except Exception as exc:
            audit_event("llm.tool_call_failed", **fields, error_type=type(exc).__name__)
            raise
        audit_event("llm.tool_call_succeeded", **fields)
    return called
