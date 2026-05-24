from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy.engine import Engine


@dataclass(frozen=True)
class SchemaRevisionState:
    current_heads: set[str]
    expected_heads: set[str]

    @property
    def is_at_head(self) -> bool:
        return self.current_heads == self.expected_heads


class SchemaOutOfDateError(RuntimeError):
    def __init__(self, state: SchemaRevisionState):
        current = ", ".join(sorted(state.current_heads)) or "none"
        expected = ", ".join(sorted(state.expected_heads)) or "none"
        super().__init__(
            "Baza nije na zadnjoj Alembic reviziji. "
            f"Current: [{current}] | Expected: [{expected}]. "
            "Pokrenite: alembic upgrade head"
        )
        self.state = state


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _alembic_config() -> Config:
    root = _project_root()
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    return config


def get_schema_revision_state(engine: Engine) -> SchemaRevisionState:
    script = ScriptDirectory.from_config(_alembic_config())
    expected_heads = set(script.get_heads())
    with engine.connect() as conn:
        context = MigrationContext.configure(conn)
        current_heads = set(context.get_current_heads())
    return SchemaRevisionState(
        current_heads=current_heads,
        expected_heads=expected_heads,
    )


def require_schema_at_head(engine: Engine) -> SchemaRevisionState:
    state = get_schema_revision_state(engine)
    if not state.is_at_head:
        raise SchemaOutOfDateError(state)
    return state
