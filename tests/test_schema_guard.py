from sqlmodel import create_engine
from sqlmodel.pool import StaticPool

from app.schema_guard import (
    SchemaOutOfDateError,
    get_schema_revision_state,
    require_schema_at_head,
)


class _DummyScriptDirectory:
    def __init__(self, heads: list[str]):
        self._heads = heads

    def get_heads(self) -> list[str]:
        return self._heads


def _memory_engine():
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def test_schema_guard_detects_outdated_database(monkeypatch):
    monkeypatch.setattr(
        "app.schema_guard.ScriptDirectory.from_config",
        lambda _cfg: _DummyScriptDirectory(["0008_add_organizations_multi_tenant"]),
    )
    engine = _memory_engine()

    state = get_schema_revision_state(engine)
    assert state.current_heads == set()
    assert state.expected_heads == {"0008_add_organizations_multi_tenant"}
    assert state.is_at_head is False


def test_schema_guard_passes_when_head_matches(monkeypatch):
    monkeypatch.setattr(
        "app.schema_guard.ScriptDirectory.from_config",
        lambda _cfg: _DummyScriptDirectory(["head-a"]),
    )
    engine = _memory_engine()

    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"
        )
        conn.exec_driver_sql(
            "INSERT INTO alembic_version (version_num) VALUES ('head-a')"
        )

    state = require_schema_at_head(engine)
    assert state.is_at_head is True


def test_schema_guard_raises_with_clear_message(monkeypatch):
    monkeypatch.setattr(
        "app.schema_guard.ScriptDirectory.from_config",
        lambda _cfg: _DummyScriptDirectory(["head-b"]),
    )
    engine = _memory_engine()

    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"
        )
        conn.exec_driver_sql(
            "INSERT INTO alembic_version (version_num) VALUES ('head-a')"
        )

    try:
        require_schema_at_head(engine)
        raise AssertionError("Expected SchemaOutOfDateError")
    except SchemaOutOfDateError as exc:
        message = str(exc)
        assert "alembic upgrade head" in message
        assert "head-a" in message
        assert "head-b" in message
