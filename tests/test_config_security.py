import pytest
from pydantic import ValidationError

from app.config import Settings


def test_secret_key_is_required_when_env_missing(monkeypatch):
    """Bez SECRET_KEY varijable konfiguracija mora pasti."""
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            ENVIRONMENT="test",
            DATABASE_URL="sqlite:///./data/test.db",
            ALGORITHM="HS256",
            ACCESS_TOKEN_EXPIRE_MINUTES=60,
        )


def test_secret_key_rejects_insecure_placeholder():
    """Poznati placeholder key se mora odbiti."""
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            ENVIRONMENT="test",
            DATABASE_URL="sqlite:///./data/test.db",
            SECRET_KEY="change-this-in-production-super-secret-key",
            ALGORITHM="HS256",
            ACCESS_TOKEN_EXPIRE_MINUTES=60,
        )


def test_secret_key_rejects_short_values():
    """Prekratki SECRET_KEY ne smije proci validaciju."""
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            ENVIRONMENT="test",
            DATABASE_URL="sqlite:///./data/test.db",
            SECRET_KEY="short-key",
            ALGORITHM="HS256",
            ACCESS_TOKEN_EXPIRE_MINUTES=60,
        )
