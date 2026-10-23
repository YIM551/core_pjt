import importlib.util
from pathlib import Path


path = (
    Path(__file__).parents[1]
    / "alembic"
    / "versions"
    / "0006_drop_candidate_profile_project.py"
)
spec = importlib.util.spec_from_file_location("migration_0006", path)
migration = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(migration)

initial_path = (
    Path(__file__).parents[1]
    / "alembic"
    / "versions"
    / "0001_initial.py"
)
initial_spec = importlib.util.spec_from_file_location("migration_0001", initial_path)
initial_migration = importlib.util.module_from_spec(initial_spec)
assert initial_spec.loader is not None
initial_spec.loader.exec_module(initial_migration)


class Inspector:
    def __init__(self, tables):
        self.tables = tables

    def get_table_names(self):
        return self.tables


def test_upgrade_drops_existing_project_and_profile_tables(monkeypatch):
    dropped = []
    monkeypatch.setattr(migration.op, "get_bind", lambda: object())
    monkeypatch.setattr(
        migration.sa,
        "inspect",
        lambda _: Inspector(["candidate_profiles", "candidate_projects"]),
    )
    monkeypatch.setattr(migration.op, "drop_table", dropped.append)

    migration.upgrade()

    assert dropped == ["candidate_projects", "candidate_profiles"]


def test_upgrade_skips_tables_that_are_absent_on_fresh_database(monkeypatch):
    monkeypatch.setattr(migration.op, "get_bind", lambda: object())
    monkeypatch.setattr(migration.sa, "inspect", lambda _: Inspector([]))
    monkeypatch.setattr(
        migration.op,
        "drop_table",
        lambda _: (_ for _ in ()).throw(AssertionError("must not drop absent table")),
    )

    migration.upgrade()


def test_downgrade_restores_empty_tables_and_indexes(monkeypatch):
    created_tables = []
    created_indexes = []
    monkeypatch.setattr(migration.op, "get_bind", lambda: object())
    monkeypatch.setattr(migration.sa, "inspect", lambda _: Inspector([]))
    monkeypatch.setattr(
        migration.op,
        "create_table",
        lambda name, *columns: created_tables.append((name, columns)),
    )
    monkeypatch.setattr(
        migration.op,
        "create_index",
        lambda name, table, columns, unique=False: created_indexes.append(
            (name, table, columns, unique)
        ),
    )

    migration.downgrade()

    assert [name for name, _ in created_tables] == [
        "candidate_profiles",
        "candidate_projects",
    ]
    assert created_indexes == [
        (
            "ix_candidate_profiles_user_id",
            "candidate_profiles",
            ["user_id"],
            True,
        ),
        (
            "ix_candidate_projects_user_id",
            "candidate_projects",
            ["user_id"],
            False,
        ),
    ]


def test_full_downgrade_chain_removes_legacy_candidate_tables(monkeypatch):
    tables = set()
    dropped = []

    monkeypatch.setattr(migration.op, "get_bind", lambda: object())
    monkeypatch.setattr(
        migration.sa,
        "inspect",
        lambda _: Inspector(list(tables)),
    )
    monkeypatch.setattr(
        migration.op,
        "create_table",
        lambda name, *columns: tables.add(name),
    )
    monkeypatch.setattr(migration.op, "create_index", lambda *args, **kwargs: None)

    migration.downgrade()

    assert {"candidate_profiles", "candidate_projects"} <= tables

    monkeypatch.setattr(initial_migration.op, "get_bind", lambda: object())
    def drop_metadata(bind):
        assert {"candidate_profiles", "candidate_projects"} <= tables
        tables.clear()

    monkeypatch.setattr(initial_migration.HISTORICAL_METADATA, "drop_all", drop_metadata)

    initial_migration.downgrade()

    assert tables == set()
