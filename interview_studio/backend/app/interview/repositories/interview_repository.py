from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.entity_registry import InterviewEvaluation, InterviewMemorySummary, InterviewMessage, InterviewSession


class InterviewRepository:
    def __init__(self, db: Session):
        self.db = db

    def session(self, session_id: int, user_id: int, company_id: int, status: str | None = None, for_update: bool = False) -> InterviewSession | None:
        statement = select(InterviewSession).where(InterviewSession.id == session_id, InterviewSession.user_id == user_id, InterviewSession.company_id == company_id, InterviewSession.job_posting_id.is_(None), InterviewSession.deleted_at.is_(None))
        if status is not None:
            statement = statement.where(InterviewSession.status == status)
        if for_update:
            statement = statement.with_for_update()
        return self.db.scalar(statement)

    def messages(self, session_id: int) -> list[InterviewMessage]:
        return list(self.db.scalars(select(InterviewMessage).where(InterviewMessage.interview_session_id == session_id).order_by(InterviewMessage.sequence_number)).all())

    def recent_messages(self, session_id: int, limit: int = 20) -> list[InterviewMessage]:
        rows = self.db.scalars(
            select(InterviewMessage).where(InterviewMessage.interview_session_id == session_id)
            .order_by(InterviewMessage.sequence_number.desc()).limit(limit)
        ).all()
        return list(reversed(rows))

    def sessions(self, user_id: int, company_id: int) -> list[InterviewSession]:
        stmt = select(InterviewSession).where(InterviewSession.user_id == user_id, InterviewSession.company_id == company_id, InterviewSession.job_posting_id.is_(None), InterviewSession.deleted_at.is_(None)).order_by(InterviewSession.created_at.desc())
        return list(self.db.scalars(stmt))

    def evaluations(self, session_id: int) -> list[InterviewEvaluation]:
        stmt = select(InterviewEvaluation).join(InterviewMessage).where(InterviewMessage.interview_session_id == session_id)
        return list(self.db.scalars(stmt))

    def add_session(self, **values) -> InterviewSession:
        item = InterviewSession(**values); self.db.add(item); return item

    def add_message(self, **values) -> InterviewMessage:
        item = InterviewMessage(**values); self.db.add(item); return item

    def add_evaluation(self, **values) -> InterviewEvaluation:
        item = InterviewEvaluation(**values); self.db.add(item); return item

    def latest_memory_summaries(self, session_id: int, limit: int = 4) -> list[InterviewMemorySummary]:
        """Newest summaries in chronological order for direct model context."""
        rows = self.db.scalars(
            select(InterviewMemorySummary)
            .where(InterviewMemorySummary.interview_session_id == session_id)
            .order_by(InterviewMemorySummary.end_sequence_number.desc())
            .limit(limit)
        ).all()
        return list(reversed(rows))

    def memory_summary(self, session_id: int, end_sequence_number: int) -> InterviewMemorySummary | None:
        return self.db.scalar(
            select(InterviewMemorySummary).where(
                InterviewMemorySummary.interview_session_id == session_id,
                InterviewMemorySummary.end_sequence_number == end_sequence_number,
            )
        )

    def add_memory_summary(self, **values) -> InterviewMemorySummary:
        item = InterviewMemorySummary(**values)
        self.db.add(item)
        return item

    def older_similar_memory_summaries(
        self, session_id: int, vector: list[float], exclude_end_sequences: set[int], limit: int = 3,
    ) -> list[InterviewMemorySummary]:
        """Vector search is always constrained to this exact interview session."""
        distance = InterviewMemorySummary.embedding.cosine_distance(vector)
        stmt = select(InterviewMemorySummary).where(
            InterviewMemorySummary.interview_session_id == session_id,
            InterviewMemorySummary.embedding.is_not(None),
        )
        if exclude_end_sequences:
            stmt = stmt.where(InterviewMemorySummary.end_sequence_number.not_in(exclude_end_sequences))
        return list(self.db.scalars(stmt.order_by(distance).limit(limit)).all())

    def completed_memory_blocks(self, session_id: int) -> list[tuple[int, int, list[InterviewMessage]]]:
        """Return only full ten-pair blocks with candidate/interviewer message order."""
        rows = self.messages(session_id)
        pairs: list[tuple[InterviewMessage, InterviewMessage]] = []
        index = 0
        while index + 1 < len(rows):
            candidate, interviewer = rows[index], rows[index + 1]
            if candidate.speaker == "CANDIDATE" and interviewer.speaker == "INTERVIEWER":
                pairs.append((candidate, interviewer))
                index += 2
            else:
                index += 1
        blocks: list[tuple[int, int, list[InterviewMessage]]] = []
        for start in range(0, len(pairs) - 9, 10):
            block_pairs = pairs[start:start + 10]
            messages = [message for pair in block_pairs for message in pair]
            blocks.append((messages[0].sequence_number, messages[-1].sequence_number, messages))
        return blocks
