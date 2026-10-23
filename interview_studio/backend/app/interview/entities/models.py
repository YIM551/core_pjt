from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, JSON, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from app.auth.entities.base import Timestamped
from app.core.database import Base


class InterviewSession(Timestamped):
    __tablename__ = "interview_sessions"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    job_posting_id: Mapped[int | None] = mapped_column(ForeignKey("job_postings.id"))
    target_role: Mapped[str] = mapped_column(String(30))
    interview_type: Mapped[str] = mapped_column(String(50), default="COMPREHENSIVE")
    difficulty: Mapped[str] = mapped_column(String(50), default="INTERMEDIATE")
    status: Mapped[str] = mapped_column(String(30), default="IN_PROGRESS")
    overall_score: Mapped[float | None] = mapped_column(Float)
    summary: Mapped[str | None] = mapped_column(Text)


class InterviewMessage(Base):
    __tablename__ = "interview_messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    interview_session_id: Mapped[int] = mapped_column(ForeignKey("interview_sessions.id"), index=True)
    sequence_number: Mapped[int] = mapped_column(Integer)
    speaker: Mapped[str] = mapped_column(String(20))
    question_type: Mapped[str | None] = mapped_column(String(50))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class InterviewEvaluation(Base):
    __tablename__ = "interview_evaluations"
    id: Mapped[int] = mapped_column(primary_key=True)
    interview_message_id: Mapped[int] = mapped_column(ForeignKey("interview_messages.id"), unique=True)
    scores: Mapped[dict] = mapped_column(JSON, default=dict)
    total_score: Mapped[float] = mapped_column(Float)
    strengths: Mapped[list] = mapped_column(JSON, default=list)
    weaknesses: Mapped[list] = mapped_column(JSON, default=list)
    missing_points: Mapped[list] = mapped_column(JSON, default=list)
    improvement_advice: Mapped[str] = mapped_column(Text)
    improved_answer: Mapped[str] = mapped_column(Text)
    follow_up_question: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class InterviewMemorySummary(Base):
    """A compact, session-scoped summary used as mid- and long-term memory."""

    __tablename__ = "interview_memory_summaries"
    __table_args__ = (
        UniqueConstraint(
            "interview_session_id",
            "end_sequence_number",
            name="uq_interview_memory_summaries_session_end_sequence",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    interview_session_id: Mapped[int] = mapped_column(
        ForeignKey("interview_sessions.id"), index=True
    )
    start_sequence_number: Mapped[int] = mapped_column(Integer)
    end_sequence_number: Mapped[int] = mapped_column(Integer)
    summary: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(4096))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
