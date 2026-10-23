from enum import StrEnum

from typing import Literal

from datetime import datetime
from pydantic import BaseModel, Field, field_validator

from app.shared.http.dto import RequestDTO


class TargetRole(StrEnum):
    FRONTEND = "FRONTEND"
    BACKEND = "BACKEND"
    DATA_AI = "DATA_AI"
    EMBEDDED = "EMBEDDED"
    INFRA = "INFRA"
    PM = "PM"


class InterviewCreateRequest(RequestDTO):
    target_role: TargetRole
    interview_type: Literal["COMPREHENSIVE"] = "COMPREHENSIVE"
    difficulty: Literal["BEGINNER", "INTERMEDIATE", "ADVANCED"] = "INTERMEDIATE"


class InterviewMessageRequest(RequestDTO):
    content: str = Field(min_length=1, max_length=5000)

    @field_validator("content", mode="before")
    @classmethod
    def trim_content(cls, value):
        return value.strip() if isinstance(value, str) else value


class EvaluationDTO(RequestDTO):
    scores: dict[str, float] = Field(default_factory=dict)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    missing_points: list[str] = Field(default_factory=list)
    improvement_advice: str
    improved_answer: str
    follow_up_question: str

    @field_validator("scores")
    @classmethod
    def score_range(cls, value):
        if any(score < 0 or score > 100 for score in value.values()):
            raise ValueError("scores must be between 0 and 100")
        return value


class InterviewTurnResultDTO(RequestDTO):
    intent: Literal["ANSWER", "CLARIFICATION", "CANDIDATE_QUESTION", "OTHER"]
    interviewer_reply: str
    next_phase: Literal["ICEBREAKER", "INTERVIEW"]
    evaluation: EvaluationDTO | None = None

    @field_validator("interviewer_reply")
    @classmethod
    def reply_required(cls, value):
        if not value.strip():
            raise ValueError("interviewer_reply is required")
        return value


class InterviewTurnResult(InterviewTurnResultDTO):
    """Internal agent result. It is never serialized directly as an API DTO."""
    evidence_sources: list[dict[str, str]] = Field(default_factory=list)
    fallback_used: bool = False


class InterviewReportSummaryDTO(RequestDTO):
    """Schema-constrained internal result for report generation."""

    summary: str = Field(min_length=1)

    @field_validator("summary")
    @classmethod
    def summary_required(cls, value):
        if not value.strip():
            raise ValueError("summary is required")
        return value


class InterviewMemorySummaryDTO(RequestDTO):
    """Internal-only schema for compact structured memory summarisation."""

    candidate_experiences_and_claims: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    unresolved_follow_ups: list[str] = Field(default_factory=list)


class InterviewSessionResponse(BaseModel):
    model_config = {"from_attributes": True}
    id: int; target_role: str; interview_type: str; difficulty: str; status: str
    overall_score: float | None = None; summary: str | None = None


class InterviewMessageResponse(BaseModel):
    model_config = {"from_attributes": True}
    id: int; sequence_number: int; speaker: str; question_type: str | None = None; content: str
    created_at: datetime | None = None


class InterviewTurnResponse(BaseModel):
    candidate_message: InterviewMessageResponse
    interviewer_message: InterviewMessageResponse
    sources: list[dict[str, str]] = Field(default_factory=list)


class InterviewDetailResponse(BaseModel):
    session: InterviewSessionResponse
    messages: list[InterviewMessageResponse]


class InterviewReportResponse(BaseModel):
    session: InterviewSessionResponse
    overall_score: float | None = None
    summary: str | None = None
    evaluations: list[dict] = Field(default_factory=list)
