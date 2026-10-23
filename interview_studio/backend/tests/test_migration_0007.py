import importlib.util
from pathlib import Path


path = Path(__file__).parents[1] / "alembic" / "versions" / "0007_interview_memory_summaries.py"
spec = importlib.util.spec_from_file_location("migration_0007", path)
migration = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(migration)

initial_path = Path(__file__).parents[1] / "alembic" / "versions" / "0001_initial.py"
initial_spec = importlib.util.spec_from_file_location("migration_0001", initial_path)
initial_migration = importlib.util.module_from_spec(initial_spec)
assert initial_spec.loader is not None
initial_spec.loader.exec_module(initial_migration)


class Inspector:
    def __init__(self, tables):
        self.tables = tables

    def get_table_names(self):
        return self.tables


def test_upgrade_creates_session_scoped_memory_summary_table(monkeypatch):
    created = []
    indexed = []
    monkeypatch.setattr(migration.op, "get_bind", lambda: object())
    monkeypatch.setattr(migration.sa, "inspect", lambda _: Inspector([]))
    monkeypatch.setattr(migration.op, "create_table", lambda name, *columns: created.append((name, columns)))
    monkeypatch.setattr(migration.op, "create_index", lambda *values, **_: indexed.append(values))

    migration.upgrade()

    assert created[0][0] == "interview_memory_summaries"
    assert indexed == [
        (
            "ix_interview_memory_summaries_interview_session_id",
            "interview_memory_summaries",
            ["interview_session_id"],
        )
    ]


def test_downgrade_drops_only_memory_summary_table(monkeypatch):
    dropped = []
    monkeypatch.setattr(migration.op, "get_bind", lambda: object())
    monkeypatch.setattr(migration.sa, "inspect", lambda _: Inspector(["interview_memory_summaries"]))
    monkeypatch.setattr(migration.op, "drop_table", dropped.append)

    migration.downgrade()

    assert dropped == ["interview_memory_summaries"]


def test_historical_initial_schema_does_not_create_a_later_memory_table():
    assert "interview_memory_summaries" not in initial_migration.HISTORICAL_METADATA.tables
    assert "interview_memory_summaries" in migration.revision


def test_fresh_revision_path_creates_memory_table_only_at_0007(monkeypatch):
    created_initial = []
    created_0007 = []
    monkeypatch.setattr(initial_migration.op, "get_bind", lambda: type("Bind", (), {"dialect": type("Dialect", (), {"name": "sqlite"})()})())
    monkeypatch.setattr(initial_migration.HISTORICAL_METADATA, "create_all", lambda *, bind: created_initial.extend(initial_migration.HISTORICAL_METADATA.tables))
    initial_migration.upgrade()

    monkeypatch.setattr(migration.op, "get_bind", lambda: object())
    monkeypatch.setattr(migration.sa, "inspect", lambda _: Inspector(created_initial))
    monkeypatch.setattr(migration.op, "create_table", lambda name, *_: created_0007.append(name))
    monkeypatch.setattr(migration.op, "create_index", lambda *_, **__: None)
    migration.upgrade()

    assert "interview_memory_summaries" not in created_initial
    assert created_0007 == ["interview_memory_summaries"]


def test_0007_memory_table_lifecycle_from_fresh_0006_state(monkeypatch):
    tables = set(initial_migration.HISTORICAL_METADATA.tables)
    created = []
    dropped = []

    monkeypatch.setattr(migration.op, "get_bind", lambda: object())
    monkeypatch.setattr(migration.sa, "inspect", lambda _: Inspector(list(tables)))

    def create_table(name, *_):
        created.append(name)
        tables.add(name)

    def drop_table(name):
        dropped.append(name)
        tables.remove(name)

    monkeypatch.setattr(migration.op, "create_table", create_table)
    monkeypatch.setattr(migration.op, "create_index", lambda *_, **__: None)
    monkeypatch.setattr(migration.op, "drop_table", drop_table)

    # This represents fresh 0006: 0001's historical table set after 0005/0006
    # removals, with no memory table before 0007 runs.
    tables.discard("candidate_profiles")
    tables.discard("candidate_projects")
    tables.discard("compatibility_analyses")
    assert "interview_memory_summaries" not in tables

    migration.upgrade()
    assert "interview_memory_summaries" in tables
    migration.downgrade()
    assert "interview_memory_summaries" not in tables
    migration.upgrade()

    assert created == ["interview_memory_summaries", "interview_memory_summaries"]
    assert dropped == ["interview_memory_summaries"]
