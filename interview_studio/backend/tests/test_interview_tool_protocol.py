import json
from types import SimpleNamespace

import pytest
from langchain_core.messages import ToolMessage

from app.interview.services import agent
from app.shared.ai.runtime import append_tool_messages
from app.shared.ai.runtime import ToolCallingUnavailable
from app.interview.entities.models import InterviewMessage, InterviewEvaluation
from app.candidate.services.chat import CandidateChatService
from app.candidate.dto.chat import ChatRequest
from app.auth.entities.models import User
from app.shared.ai.runtime import ToolCallingUnavailable as SharedToolCallingUnavailable
from app.shared.ai.runtime import ToolProtocolError, failure_metadata
from app.interview.services.tools import InterviewToolContext
from app.interview.services import tools
from app.document.services import retrieval
from app.document.services.retrieval import EvidenceHit


def test_tool_call_is_converted_to_langchain_tool_message():
    class Tool:
        def invoke(self, args):
            assert args == {"query": "backend"}
            return '[{"content":"safe evidence"}]'
    messages = []
    response = SimpleNamespace(tool_calls=[{"id": "call-1", "name": "search_company_evidence", "args": {"query": "backend"}}])
    assert append_tool_messages(response, {"search_company_evidence": Tool()}, messages) == ["search_company_evidence"]
    assert isinstance(messages[0], ToolMessage)


def test_retrieval_tool_evidence_is_cleaned_per_item_instead_of_failing():
    class Tool:
        def invoke(self, _args):
            return json.dumps(
                {
                    "evidence": [
                        {
                            "category": "PERSONAL",
                            "content": "Spring 경험 [출처](https://internal.test/doc_123) /app/uploads/a.md",
                        },
                        {"category": "PERSONAL", "content": "https://only-secret.test/doc_456"},
                    ],
                    "reason": None,
                },
                ensure_ascii=False,
            )

    messages = []
    response = SimpleNamespace(tool_calls=[{
        "id": "call-safe-evidence",
        "name": "search_personal_evidence",
        "args": {"query": "ignored"},
    }])
    assert append_tool_messages(response, {"search_personal_evidence": Tool()}, messages) == ["search_personal_evidence"]
    payload = json.loads(messages[0].content)
    assert payload["evidence"] == [{"category": "PERSONAL", "content": "Spring 경험"}]
    assert "https://" not in messages[0].content
    assert "doc_123" not in messages[0].content
    assert "/app/uploads" not in messages[0].content


def test_retrieval_evidence_json_does_not_trigger_cross_json_markdown_detection():
    """A harmless code fragment must not be treated as a Markdown link in JSON."""
    class Tool:
        def invoke(self, _args):
            return json.dumps(
                {
                    "evidence": [{
                        "category": "PERSONAL",
                        # The evidence array opens with `[` in the rendered JSON;
                        # this `](` previously completed the generic Markdown
                        # regex across the JSON boundary and caused a 503.
                        "content": "배열 경계 처리는 matcher ](value) 코드로 확인했습니다.",
                    }],
                    "reason": None,
                },
                ensure_ascii=False,
            )

    messages = []
    response = SimpleNamespace(tool_calls=[{
        "id": "call-json-regression",
        "name": "search_personal_evidence",
        "args": {"query": "배열 처리"},
    }])

    assert append_tool_messages(response, {"search_personal_evidence": Tool()}, messages) == [
        "search_personal_evidence"
    ]
    payload = json.loads(messages[0].content)
    assert payload["evidence"] == [{
        "category": "PERSONAL",
        "content": "배열 경계 처리는 matcher ](value) 코드로 확인했습니다.",
    }]


def test_retrieval_tool_with_only_stripped_evidence_returns_empty_safely():
    class Tool:
        def invoke(self, _args):
            return '{"evidence":[{"category":"PERSONAL","content":"https://secret.test/doc_123"}],"reason":null}'

    messages = []
    response = SimpleNamespace(tool_calls=[{
        "id": "call-empty-evidence",
        "name": "search_personal_evidence",
        "args": {"query": "ignored"},
    }])
    append_tool_messages(response, {"search_personal_evidence": Tool()}, messages)
    assert json.loads(messages[0].content) == {
        "evidence": [], "reason": "no_relevant_evidence"
    }


def test_retrieval_log_contains_only_sanitized_delivered_evidence(monkeypatch):
    events = []
    monkeypatch.setattr(retrieval, "audit_event", lambda event, **fields: events.append((event, fields)))
    hit = EvidenceHit(
        "PERSONAL",
        SimpleNamespace(content="FastAPI [원문](https://secret.test/doc_123) /app/uploads/a.md", metadata_json={}, id=1),
        SimpleNamespace(title="candidate.md"),
        0.123456,
    )
    payload = retrieval.safe_evidence_payload([hit])
    retrieval.audit_retrieval_delivered(
        scope="PERSONAL", purpose="test", hits=[hit], payload=payload, user_id=1
    )
    assert events[0][0] == "rag.retrieval_completed"
    fields = events[0][1]
    assert fields["result_count"] == 1
    assert fields["results"] == [{
        "source": "candidate",
        "category": "PERSONAL",
        "preview": "FastAPI",
        "distance": 0.1235,
    }]
    rendered = repr(fields)
    assert "https://" not in rendered
    assert "doc_123" not in rendered
    assert "/app/uploads" not in rendered


def test_invalid_no_tool_protocol_retries_three_times(monkeypatch):
    calls = {"count": 0}
    monkeypatch.setattr(agent, "_scoped_interview_session", lambda *args: SimpleNamespace(company_id=1, id=1, target_role="BACKEND"))
    monkeypatch.setattr(agent, "make_interview_tools", lambda _: [])
    class Model:
        def bind_tools(self, _): return self
        def invoke(self, _):
            calls["count"] += 1
            return SimpleNamespace(tool_calls=[], content='{}')
    monkeypatch.setattr(agent, "_model", lambda: Model())
    with pytest.raises(ToolCallingUnavailable):
        agent.run_interview_turn("answer", [], db=object(), user_id=1, company_id=1, session_id=1)
    assert calls["count"] == 3


def test_tool_failure_does_not_construct_persisted_turn_objects(monkeypatch):
    """Protocol failure happens before the service persistence boundary."""
    calls = {"count": 0}
    monkeypatch.setattr(agent, "_scoped_interview_session", lambda *args: SimpleNamespace(company_id=1, id=1, target_role="BACKEND"))
    monkeypatch.setattr(agent, "make_interview_tools", lambda _: [])
    class Model:
        def bind_tools(self, _): return self
        def invoke(self, _): calls["count"] += 1; return SimpleNamespace(tool_calls=[], content="{}")
    monkeypatch.setattr(agent, "_model", lambda: Model())
    with pytest.raises(ToolCallingUnavailable):
        agent.run_interview_turn("answer", [], db=object(), user_id=1, company_id=1, session_id=1)
    assert calls["count"] == 3


def test_setup_failure_is_logged_three_times_without_sensitive_content(monkeypatch):
    events = []
    monkeypatch.setattr(agent, "_scoped_interview_session", lambda *args: (_ for _ in ()).throw(RuntimeError("db unavailable")))
    monkeypatch.setattr(agent, "audit_event", lambda event, **fields: events.append((event, fields)))
    with pytest.raises(ToolCallingUnavailable):
        agent.run_interview_turn("private candidate answer", [], db=object(), user_id=9, company_id=1, session_id=7)
    assert len(events) == 3
    assert [fields["attempt"] for _, fields in events] == [1, 2, 3]
    for event, fields in events:
        assert event == "llm.tool_call_failed"
        assert set(fields) == {"attempt", "stage", "reason_code", "error_type", "session_id", "user_id"}
        assert fields["stage"] == "model_invocation"
        assert fields["reason_code"] == "model_or_dependency_error"
        assert "private candidate answer" not in repr(fields)


def test_report_setup_failure_is_logged_three_times(monkeypatch):
    events = []
    monkeypatch.setattr(agent, "_scoped_interview_session", lambda *args: (_ for _ in ()).throw(RuntimeError("scope unavailable")))
    monkeypatch.setattr(agent, "audit_event", lambda event, **fields: events.append((event, fields)))
    with pytest.raises(ToolCallingUnavailable):
        agent.run_interview_report(object(), 7, "BACKEND", "COMPREHENSIVE", "INTERMEDIATE", user_id=9, company_id=1)
    assert len(events) == 3
    assert all(
        event == "llm.tool_call_failed"
        and fields["stage"] == "report_model_invocation"
        and fields["reason_code"] == "model_or_dependency_error"
        for event, fields in events
    )


def test_tool_protocol_failures_use_allow_listed_safe_reason_codes():
    stage, reason = failure_metadata(ToolProtocolError("tool arguments are invalid"))
    assert (stage, reason) == ("tool_protocol", "invalid_tool_args")
    stage, reason = failure_metadata(ToolProtocolError("required company tool was not called"))
    assert (stage, reason) == ("tool_protocol", "required_company_tool_missing")


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("no_relevant_evidence", ("company_retrieval", "company_evidence_unavailable")),
        ("retrieval_budget_exhausted", ("company_retrieval", "company_evidence_unavailable")),
        ("invalid interviewer reply", ("final_response", "invalid_interviewer_reply")),
        ("invalid evaluation score", ("final_response", "invalid_evaluation")),
        ("invalid evaluation text", ("final_response", "invalid_evaluation")),
    ],
)
def test_known_tool_protocol_failures_are_never_logged_as_raw_messages(message, expected):
    assert failure_metadata(ToolProtocolError(message)) == expected


def test_greeting_can_finish_without_company_tool(monkeypatch):
    class Context:
        personal_sources = []
        company_sources = []

    class Model:
        def bind_tools(self, _): return self
        def invoke(self, _):
            return SimpleNamespace(tool_calls=[], content="free-form readiness response")
        def with_structured_output(self, schema, *, method):
            assert schema is agent.InterviewTurnResult
            assert method == "json_schema"
            return SimpleNamespace(
                invoke=lambda _: agent.InterviewTurnResult(
                    intent="OTHER",
                    interviewer_reply="안녕하세요. 편하게 시작해 주세요.",
                    next_phase="ICEBREAKER",
                )
            )

    monkeypatch.setattr(agent, "_scoped_interview_session", lambda *args: SimpleNamespace(company_id=1, id=1, target_role="BACKEND"))
    monkeypatch.setattr(agent, "InterviewToolContext", lambda *args, **kwargs: Context())
    monkeypatch.setattr(agent, "make_interview_tools", lambda _: [])
    monkeypatch.setattr(agent, "_model", lambda: Model())
    result = agent.run_interview_turn("안녕", [], db=object(), user_id=1, company_id=1, session_id=1)
    assert result.intent == "OTHER"


def test_company_tool_with_zero_evidence_returns_safe_tool_payload(monkeypatch):
    monkeypatch.setattr("app.interview.services.tools.retrieve_company", lambda *args, **kwargs: [])
    context = InterviewToolContext(db=object(), user_id=1, company_id=1, session_id=1, target_role="BACKEND")
    expected = '{"evidence": [], "reason": "no_relevant_evidence"}'
    assert context.search_company("삼성 백엔드") == expected
    assert context.search_company("삼성 백엔드 다시 검색") == expected
    assert context.budget.used_tool_calls == 1


def test_zero_company_evidence_tool_message_can_complete_interview(monkeypatch):
    """Empty retrieval is evidence absence, not a native tool protocol failure."""
    captured_messages = []

    class Model:
        def __init__(self):
            self.calls = 0

        def bind_tools(self, _):
            return self

        def invoke(self, messages):
            self.calls += 1
            captured_messages[:] = messages
            if self.calls <= 2:
                return SimpleNamespace(
                    tool_calls=[{
                        "id": f"company-empty-{self.calls}",
                        "name": "search_company_evidence",
                        "args": {"query": "삼성 백엔드"},
                    }],
                    content="",
                )
            return SimpleNamespace(
                tool_calls=[],
                content="this is deliberately not valid json",
            )

        def with_structured_output(self, schema, *, method):
            assert schema is agent.InterviewTurnResult
            assert method == "json_schema"

            def invoke(messages):
                captured_messages[:] = messages
                return agent.InterviewTurnResult(
                    intent="CANDIDATE_QUESTION",
                    interviewer_reply=(
                        "관련 회사 근거가 부족하지만 편하게 대화를 이어갈 수 있습니다."
                    ),
                    next_phase="ICEBREAKER",
                )

            return SimpleNamespace(invoke=invoke)

    monkeypatch.setattr(
        agent,
        "_scoped_interview_session",
        lambda *args: SimpleNamespace(
            company_id=1,
            id=14,
            target_role="BACKEND",
        ),
    )
    monkeypatch.setattr(
        "app.interview.services.tools.retrieve_company",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(agent, "_model", Model)

    result = agent.run_interview_turn(
        "면접관님과 잠깐 이야기해도 될까요?",
        [],
        db=object(),
        user_id=1,
        company_id=1,
        session_id=14,
    )

    tool_messages = [
        message for message in captured_messages if isinstance(message, ToolMessage)
    ]
    assert len(tool_messages) == 2
    assert all(
        message.content == '{"evidence": [], "reason": "no_relevant_evidence"}'
        for message in tool_messages
    )
    assert result.intent == "CANDIDATE_QUESTION"
    assert "편하게 대화" in result.interviewer_reply


def test_three_schema_failures_return_503_without_persistence(monkeypatch):
    structured_calls = []

    class Model:
        def bind_tools(self, _):
            return self

        def invoke(self, _):
            return SimpleNamespace(tool_calls=[], content="model is ready")

        def with_structured_output(self, schema, *, method):
            assert schema is agent.InterviewTurnResult
            assert method == "json_schema"

            def invoke(messages):
                structured_calls.append(messages)
                return {"intent": "OTHER"}

            return SimpleNamespace(invoke=invoke)

    monkeypatch.setattr(
        agent,
        "_scoped_interview_session",
        lambda *args: SimpleNamespace(
            company_id=1,
            id=1,
            target_role="BACKEND",
        ),
    )
    monkeypatch.setattr(agent, "make_interview_tools", lambda _: [])
    monkeypatch.setattr(agent, "_model", Model)

    with pytest.raises(ToolCallingUnavailable):
        agent.run_interview_turn(
            "answer",
            [],
            db=object(),
            user_id=1,
            company_id=1,
            session_id=1,
        )

    assert len(structured_calls) == 3


def test_report_uses_history_tool_then_structured_summary(monkeypatch):
    captured_messages = []

    class HistoryTool:
        name = "read_interview_history"

        def invoke(self, args):
            assert args == {}
            return '{"messages":[],"evaluations":[]}'

    class Model:
        def __init__(self):
            self.calls = 0

        def bind_tools(self, _):
            return self

        def invoke(self, messages):
            self.calls += 1
            if self.calls == 1:
                return SimpleNamespace(
                    tool_calls=[{
                        "id": "history-1",
                        "name": "read_interview_history",
                        "args": {},
                    }],
                    content="",
                )
            return SimpleNamespace(tool_calls=[], content="not json")

        def with_structured_output(self, schema, *, method):
            assert schema is agent.InterviewReportSummaryDTO
            assert method == "json_schema"

            def invoke(messages):
                captured_messages[:] = messages
                return agent.InterviewReportSummaryDTO(summary="종합 면접 리포트")

            return SimpleNamespace(invoke=invoke)

    monkeypatch.setattr(
        agent,
        "_scoped_interview_session",
        lambda *args: SimpleNamespace(
            user_id=1,
            company_id=1,
            id=14,
            target_role="BACKEND",
        ),
    )
    monkeypatch.setattr(agent, "InterviewToolContext", lambda *args, **kwargs: object())
    monkeypatch.setattr(agent, "make_interview_tools", lambda _: [HistoryTool()])
    monkeypatch.setattr(agent, "_model", Model)

    summary = agent.run_interview_report(
        object(),
        14,
        "BACKEND",
        "COMPREHENSIVE",
        "INTERMEDIATE",
        user_id=1,
        company_id=1,
    )

    assert summary == "종합 면접 리포트"
    assert any(isinstance(message, ToolMessage) for message in captured_messages)


def test_actual_interview_protocol_failure_logs_three_safe_attempts(monkeypatch):
    events = []

    class Context:
        personal_sources = []
        company_sources = []

    class Model:
        def bind_tools(self, _): return self
        def invoke(self, _): return SimpleNamespace(tool_calls=[], content="{}")
        def with_structured_output(self, schema, *, method):
            return SimpleNamespace(invoke=lambda _: {"intent": "OTHER"})

    monkeypatch.setattr(agent, "_scoped_interview_session", lambda *args: SimpleNamespace(company_id=1, id=1, target_role="BACKEND"))
    monkeypatch.setattr(agent, "InterviewToolContext", lambda *args, **kwargs: Context())
    monkeypatch.setattr(agent, "make_interview_tools", lambda _: [])
    monkeypatch.setattr(agent, "_model", lambda: Model())
    monkeypatch.setattr(agent, "audit_event", lambda event, **fields: events.append((event, fields)))
    with pytest.raises(ToolCallingUnavailable):
        agent.run_interview_turn("private answer", [], db=object(), user_id=9, company_id=1, session_id=7)
    assert [fields["attempt"] for _, fields in events] == [1, 2, 3]
    assert all(
        event == "llm.tool_call_failed"
        and set(fields) == {"attempt", "stage", "reason_code", "error_type", "session_id", "user_id"}
        and fields["stage"] == "final_response"
        and fields["reason_code"] == "invalid_final_json"
        and "private answer" not in repr(fields)
        for event, fields in events
    )


def test_candidate_chat_setup_failure_is_logged_three_times(monkeypatch):
    from app.candidate.services import chat
    events = []
    monkeypatch.setattr(chat, "_PersonalToolContext", lambda *args: (_ for _ in ()).throw(RuntimeError("setup unavailable")))
    monkeypatch.setattr(chat, "audit_event", lambda event, **fields: events.append((event, fields)))
    with pytest.raises(SharedToolCallingUnavailable):
        CandidateChatService(object()).answer(User(id=9, email="safe@test", name="safe"), ChatRequest(question="private question"))
    assert len(events) == 3
    assert all(
        set(fields) == {"attempt", "stage", "reason_code", "error_type", "user_id"}
        and fields["stage"] == "candidate_model_invocation"
        and fields["reason_code"] == "model_or_dependency_error"
        for _, fields in events
    )


def test_history_tool_preserves_repository_chronological_message_order(monkeypatch):
    rows = [
        SimpleNamespace(speaker="CANDIDATE", content="first"),
        SimpleNamespace(speaker="INTERVIEWER", content="second"),
    ]

    class Repository:
        def __init__(self, _):
            pass

        def recent_messages(self, session_id):
            assert session_id == 3
            return rows

        def evaluations(self, session_id):
            assert session_id == 3
            return []

    monkeypatch.setattr(tools, "InterviewRepository", Repository)
    payload = json.loads(
        InterviewToolContext(object(), 1, 1, 3, "BACKEND").history()
    )
    assert payload["messages"] == [
        {"speaker": "CANDIDATE", "content": "first"},
        {"speaker": "INTERVIEWER", "content": "second"},
    ]
