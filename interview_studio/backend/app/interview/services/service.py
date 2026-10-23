from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Any

from sqlalchemy.orm import Session

from app.auth.entities.models import User
from app.company_corpus.constants import SAMSUNG_COMPANY_NAME
from app.company_corpus.repositories.company_repository import CompanyRepository
from app.core.entity_registry import Company
from app.interview.dto.models import InterviewCreateRequest, InterviewMessageRequest
from app.interview.entities.models import InterviewMessage, InterviewSession
from app.interview.repositories.interview_repository import InterviewRepository
from app.interview.services import agent as interview_agent
from app.interview.services.memory import persist_due_summaries
from app.interview.exceptions import (
    CompanyEvidenceUnavailable,
    InterviewNotCompleted,
    InterviewNotFound,
)
from app.shared.utils.serialization import dump


@dataclass(frozen=True)
class PreparedInterviewTurn:
    """Domain result prepared by the agent and persisted by the service on demand."""

    session: InterviewSession
    messages: list[InterviewMessage]
    candidate_content: str
    result: Any


class InterviewService:
    """Transaction-owning, HTTP-free interview application service."""

    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user
        self.repository = InterviewRepository(db)

    def _company(self) -> Company:
        company = CompanyRepository(self.db).by_name(SAMSUNG_COMPANY_NAME)
        if company is None:
            raise CompanyEvidenceUnavailable()
        return company

    def _session(self, session_id: int, *, active: bool = False) -> InterviewSession:
        company = self._company()
        session = self.repository.session(
            session_id, self.user.id, company.id, "IN_PROGRESS" if active else None, active
        )
        if session is None:
            raise InterviewNotFound()
        return session

    def create(self, payload: InterviewCreateRequest) -> dict[str, Any]:
        company = self._company()
        session = self.repository.add_session(
            user_id=self.user.id,
            company_id=company.id,
            job_posting_id=None,
            target_role=payload.target_role.value,
            interview_type=payload.interview_type,
            difficulty=payload.difficulty,
        )
        try:
            self.db.commit()
            self.db.refresh(session)
        except Exception:
            self.db.rollback()
            raise
        return {"session": dump(session), "messages": []}

    def list(self) -> list[dict[str, Any]]:
        company = self._company()
        return [dump(row) for row in self.repository.sessions(self.user.id, company.id)]

    def detail(self, session_id: int) -> dict[str, Any]:
        session = self._session(session_id)
        return {"session": dump(session), "messages": [dump(item) for item in self.repository.messages(session.id)]}

    def prepare_message(self, session_id: int, payload: InterviewMessageRequest) -> PreparedInterviewTurn:
        # Retry any complete block whose best-effort summary/embedding failed on
        # a prior turn before the current turn gets its memory context.
        # Do this before acquiring the active-session row lock; creating a summary
        # owns its own commit and must not release the lock used for sequencing.
        previous_session = self._session(session_id)
        if previous_session.status == "IN_PROGRESS":
            persist_due_summaries(self.db, previous_session, self.user.id)
        session = self._session(session_id, active=True)
        messages = self.repository.messages(session.id)
        result = interview_agent.run_interview_turn(
            payload.content,
            messages,
            target_role=session.target_role,
            interview_type=session.interview_type,
            difficulty=session.difficulty,
            phase="INTERVIEW",
            icebreaker_count=0,
            db=self.db,
            user_id=self.user.id,
            company_id=session.company_id,
            session_id=session.id,
        )
        return PreparedInterviewTurn(session, messages, payload.content, result)

    def persist_message(self, prepared: PreparedInterviewTurn) -> dict[str, Any]:
        try:
            sequence = max((item.sequence_number for item in prepared.messages), default=0) + 1
            candidate = self.repository.add_message(
                interview_session_id=prepared.session.id,
                sequence_number=sequence,
                speaker="CANDIDATE",
                question_type=prepared.result.intent,
                content=prepared.candidate_content,
            )
            self.db.flush()
            if prepared.result.evaluation is not None:
                scores = {
                    key: min(100.0, max(0.0, float(value)))
                    for key, value in prepared.result.evaluation.scores.items()
                }
                self.repository.add_evaluation(
                    interview_message_id=candidate.id,
                    scores=scores,
                    total_score=mean(scores.values()) if scores else 0.0,
                    strengths=prepared.result.evaluation.strengths,
                    weaknesses=prepared.result.evaluation.weaknesses,
                    missing_points=prepared.result.evaluation.missing_points,
                    improvement_advice=prepared.result.evaluation.improvement_advice,
                    improved_answer=prepared.result.evaluation.improved_answer,
                    follow_up_question=prepared.result.evaluation.follow_up_question,
                )
            interviewer = self.repository.add_message(
                interview_session_id=prepared.session.id,
                sequence_number=sequence + 1,
                speaker="INTERVIEWER",
                question_type=prepared.result.next_phase,
                content=prepared.result.interviewer_reply,
            )
            self.db.commit()
            self.db.refresh(candidate)
            self.db.refresh(interviewer)
        except Exception:
            self.db.rollback()
            raise
        # This happens strictly after the normal candidate/interviewer commit.
        # Summary or embedding outages are observable but cannot erase a turn.
        persist_due_summaries(self.db, prepared.session, self.user.id)
        return {
            "candidate_message": dump(candidate),
            "interviewer_message": dump(interviewer),
            "sources": prepared.result.evidence_sources,
        }

    def send(self, session_id: int, payload: InterviewMessageRequest) -> dict[str, Any]:
        return self.persist_message(self.prepare_message(session_id, payload))

    def rollback(self) -> None:
        self.db.rollback()

    def finish(self, session_id: int) -> dict[str, Any]:
        session = self._session(session_id)
        if session.status == "COMPLETED":
            return dump(session)
        evaluations = self.repository.evaluations(session.id)
        if evaluations:
            session.overall_score = round(mean(item.total_score for item in evaluations), 1)
            session.summary = interview_agent.run_interview_report(
                db=self.db,
                session_id=session.id,
                user_id=self.user.id,
                company_id=session.company_id,
                target_role=session.target_role,
                interview_type=session.interview_type,
                difficulty=session.difficulty,
            )
        session.status = "COMPLETED"
        try:
            self.db.commit()
            self.db.refresh(session)
        except Exception:
            self.db.rollback()
            raise
        return dump(session)

    def report(self, session_id: int) -> dict[str, Any]:
        session = self._session(session_id)
        if session.status != "COMPLETED":
            raise InterviewNotCompleted()
        evaluations = self.repository.evaluations(session.id)
        return {
            "session": dump(session),
            "overall_score": session.overall_score,
            "summary": session.summary,
            "evaluations": [dump(item) for item in evaluations],
        }
