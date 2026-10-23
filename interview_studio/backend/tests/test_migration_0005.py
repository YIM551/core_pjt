import importlib.util
from pathlib import Path


path = Path(__file__).parents[1] / "alembic" / "versions" / "0005_drop_compatibility_analysis.py"
spec = importlib.util.spec_from_file_location("migration_0005", path)
migration = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(migration)


def test_upgrade_skips_fresh_database_without_retired_table(monkeypatch):
    class Inspector:
        def get_table_names(self): return []
    monkeypatch.setattr(migration.op, "get_bind", lambda: object())
    monkeypatch.setattr(migration.sa, "inspect", lambda _: Inspector())
    monkeypatch.setattr(migration.op, "drop_table", lambda _: (_ for _ in ()).throw(AssertionError("must not drop absent table")))
    migration.upgrade()


def test_downgrade_recreates_empty_retired_table_when_absent(monkeypatch):
    class Inspector:
        def get_table_names(self): return []
    created = []
    monkeypatch.setattr(migration.op, "get_bind", lambda: object())
    monkeypatch.setattr(migration.sa, "inspect", lambda _: Inspector())
    monkeypatch.setattr(migration.op, "create_table", lambda name, *columns: created.append((name, columns)))
    migration.downgrade()
    assert created and created[0][0] == "compatibility_analyses"
