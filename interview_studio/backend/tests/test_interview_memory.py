from types import SimpleNamespace

from langchain_core.messages import SystemMessage
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.auth.entities.models import User
from app.company_corpus.entities.models import Company
from app.core import entity_registry  # noqa: F401
from app.core.database import Base
from app.interview.dto.models import InterviewCreateRequest, InterviewMessageRequest, InterviewTurnResult
from app.interview.entities.models import InterviewMemorySummary
from app.interview.services import memory
from app.interview.services import agent
from app.interview.services.service import InterviewService


def _db_with_session(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    user = User(email="memory@test", name="memory")
    company = Company(name="삼성전자")
    db.add_all([user, company])
    db.commit()
    monkeypatch.setattr(
        "app.interview.services.agent.run_interview_turn",
        lambda *args, **kwargs: InterviewTurnResult(
            intent="ANSWER", interviewer_reply="다음 답변을 들려주세요.", next_phase="INTERVIEW"
        ),
    )
    service = InterviewService(db, user)
    session_id = service.create(InterviewCreateRequest(target_role="BACKEND"))["session"]["id"]
    return db, service, session_id


def test_summary_is_created_only_after_ten_complete_pairs(monkeypatch):
    db, service, session_id = _db_with_session(monkeypatch)
    calls = []
    monkeypatch.setattr(memory, "summarize_block", lambda rows: calls.append(rows) or "지원자 경험·주장: API 구현")
    monkeypatch.setattr(memory, "embedding", lambda _: [0.1] * 4096)

    for index in range(9):
        service.send(session_id, InterviewMessageRequest(content=f"answer {index}"))
    assert db.query(InterviewMemorySummary).count() == 0

    service.send(session_id, InterviewMessageRequest(content="answer 9"))
    stored = db.query(InterviewMemorySummary).one()
    assert (stored.start_sequence_number, stored.end_sequence_number) == (1, 20)
    assert len(calls) == 1 and len(calls[0]) == 20


def test_failed_memory_summary_does_not_erase_turn_and_retries(monkeypatch):
    db, service, session_id = _db_with_session(monkeypatch)
    attempts = {"count": 0}

    def flaky_summary(_):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("LLM unavailable")
        return "지원자 경험·주장: 재시도 성공"

    monkeypatch.setattr(memory, "summarize_block", flaky_summary)
    monkeypatch.setattr(memory, "embedding", lambda _: [0.1] * 4096)
    for index in range(10):
        service.send(session_id, InterviewMessageRequest(content=f"answer {index}"))

    # The tenth persisted turn remains even when its post-commit memory work failed.
    assert len(service.detail(session_id)["messages"]) == 20
    assert db.query(InterviewMemorySummary).count() == 0
    service.send(session_id, InterviewMessageRequest(content="next answer"))
    assert db.query(InterviewMemorySummary).count() == 1
    assert attempts["count"] >= 2


def test_memory_context_bounds_latest_and_session_scoped_long_search(monkeypatch):
    messages = [
        SimpleNamespace(speaker="CANDIDATE", content=f"candidate {index}")
        for index in range(20)
    ]
    latest = [SimpleNamespace(end_sequence_number=index, summary=f"recent {index}") for index in range(1, 5)]
    older = [SimpleNamespace(summary=f"older {index}") for index in range(3)]
    calls = {}

    class Repository:
        def __init__(self, _):
            pass

        def recent_messages(self, session_id, limit):
            calls["recent"] = (session_id, limit)
            return messages

        def latest_memory_summaries(self, session_id, limit):
            calls["latest"] = (session_id, limit)
            return latest

        def older_similar_memory_summaries(self, session_id, vector, excluded, limit):
            calls["older"] = (session_id, vector, excluded, limit)
            return older

    monkeypatch.setattr(memory, "InterviewRepository", Repository)
    monkeypatch.setattr(memory, "embed_query", lambda _: [0.5] * 4096)
    context = memory.build_memory_context(object(), 77, "latest candidate answer")

    assert len(context.short) == 20
    assert context.mid == ["recent 1", "recent 2", "recent 3", "recent 4"]
    assert context.long == ["older 0", "older 1", "older 2"]
    assert calls["recent"] == (77, 20)
    assert calls["latest"] == (77, 4)
    assert calls["older"][0] == 77
    assert calls["older"][2] == {1, 2, 3, 4}
    assert calls["older"][3] == 3


def test_long_memory_failure_keeps_direct_short_and_mid_memory(monkeypatch):
    messages = [SimpleNamespace(speaker="CANDIDATE", content="recent answer")]
    latest = [SimpleNamespace(end_sequence_number=20, summary="recent summary")]
    audits = []

    class Repository:
        def __init__(self, _):
            pass

        def recent_messages(self, session_id, limit):
            assert (session_id, limit) == (77, 20)
            return messages

        def latest_memory_summaries(self, session_id, limit):
            assert (session_id, limit) == (77, 4)
            return latest

        def older_similar_memory_summaries(self, *_):
            raise AssertionError("must not reach vector search after embedding failure")

    monkeypatch.setattr(memory, "InterviewRepository", Repository)
    monkeypatch.setattr(memory, "embed_query", lambda _: (_ for _ in ()).throw(RuntimeError("offline")))
    monkeypatch.setattr(memory, "audit_event", lambda event, **fields: audits.append((event, fields)))

    context = memory.build_memory_context(object(), 77, "new answer", user_id=9)

    assert context.short == ["지원자: recent answer"]
    assert context.mid == ["recent summary"]
    assert context.long == []
    assert audits == [
        ("rag.retrieval_failed", {
            "scope": "INTERVIEW_LONG_MEMORY",
            "purpose": "interview_long_memory",
            "error_type": "RuntimeError",
            "session_id": 77,
            "user_id": 9,
        }),
        ("interview.memory_context_failed", {
            "attempt": 1,
            "stage": "long_memory",
            "error_type": "RuntimeError",
            "session_id": 77,
            "user_id": 9,
        })
    ]


def test_unexpected_memory_summary_integrity_error_is_audited(monkeypatch):
    audits = []

    class Repository:
        def __init__(self, _):
            pass

        def completed_memory_blocks(self, _):
            return [(1, 20, [SimpleNamespace()])]

        def memory_summary(self, *_):
            return None

        def add_memory_summary(self, **_):
            return None

    class Db:
        def commit(self):
            raise IntegrityError("INSERT", {}, Exception("different constraint"))

        def rollback(self):
            pass

    monkeypatch.setattr(memory, "InterviewRepository", Repository)
    monkeypatch.setattr(memory, "summarize_block", lambda _: "summary")
    monkeypatch.setattr(memory, "embedding", lambda _: [0.1] * 4096)
    monkeypatch.setattr(memory, "audit_event", lambda event, **fields: audits.append((event, fields)))

    memory.persist_due_summaries(Db(), SimpleNamespace(id=77), user_id=9)

    assert audits == [
        ("interview.memory_summary_failed", {
            "attempt": 1,
            "stage": "persist",
            "error_type": "IntegrityError",
            "session_id": 77,
            "user_id": 9,
        })
    ]


def test_agent_merges_server_memory_into_the_single_leading_system_message(monkeypatch):
    tool_messages = []
    structured_messages = []

    class Context:
        personal_sources = []
        company_sources = []

    class MemoryContext:
        def system_content(self):
            return "[SHORT_MEMORY]\n- 지원자: 이전 답변"

    class CapturingStructured:
        def __init__(self, invoke):
            self._invoke = invoke

        def invoke(self, messages):
            structured_messages[:] = messages
            return self._invoke(messages)

    class Model:
        def bind_tools(self, _):
            return self

        def invoke(self, messages):
            tool_messages[:] = messages
            return SimpleNamespace(tool_calls=[])

        def with_structured_output(self, schema, *, method):
            return CapturingStructured(
                invoke=lambda _: {
                    "intent": "ANSWER",
                    "interviewer_reply": "한 가지 경험을 더 말씀해 주세요.",
                    "next_phase": "INTERVIEW",
                    "evaluation": None,
                }
            )

    monkeypatch.setattr(agent, "_scoped_interview_session", lambda *args: SimpleNamespace(company_id=1, id=7, target_role="BACKEND"))
    monkeypatch.setattr(agent, "InterviewToolContext", lambda *args, **kwargs: Context())
    monkeypatch.setattr(agent, "make_interview_tools", lambda _: [])
    monkeypatch.setattr(agent, "build_memory_context", lambda *args, **kwargs: MemoryContext())
    monkeypatch.setattr(agent, "_model", Model)

    agent.run_interview_turn("이번 답변", [], db=object(), user_id=1, company_id=1, session_id=7)

    for messages in (tool_messages, structured_messages):
        system_messages = [item for item in messages if isinstance(item, SystemMessage)]
        assert len(system_messages) == 1
        assert messages[0] is system_messages[0]
        assert "[SHORT_MEMORY]\n- 지원자: 이전 답변" in system_messages[0].content
        assert messages[-1].content == "이번 답변"
