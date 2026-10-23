from sqlalchemy.dialects import postgresql

from app.interview.repositories.interview_repository import InterviewRepository


class _Rows:
    def all(self):
        return []


class _RecordingSession:
    def __init__(self):
        self.statement = None

    def scalars(self, statement):
        self.statement = statement
        return _Rows()


def test_older_vector_memory_search_is_session_scoped_and_excludes_latest_four():
    """Exercise the real repository query, including its vector-search boundaries."""
    db = _RecordingSession()
    repository = InterviewRepository(db)

    assert repository.older_similar_memory_summaries(17, [0.1] * 4096, {20, 40, 60, 80}) == []

    compiled = db.statement.compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert "interview_memory_summaries.interview_session_id" in sql
    assert "NOT IN" in sql
    assert "<=>" in sql
    assert 17 in compiled.params.values()
    assert any(
        set(value) == {20, 40, 60, 80}
        for value in compiled.params.values()
        if isinstance(value, (list, tuple, set))
    )
