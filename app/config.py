from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    DATABASE_URL: str = "sqlite:///./data/menza.db"
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    RATE_LIMITER_BACKEND: str = "memory"  # memory | redis
    LOGIN_RATE_LIMIT_MAX: int = 5
    LOGIN_RATE_LIMIT_WINDOW_SECONDS: int = 60
    REDIS_URL: str | None = None
    REDIS_RATE_LIMIT_PREFIX: str = "rl:login"

    # Logging
    LOG_FILE_PATH: str | None = None
    LOG_ROTATION: str = "size"  # size | time
    LOG_FILE_MAX_BYTES: int = 10_000_000
    LOG_FILE_BACKUP_COUNT: int = 5
    LOG_RETENTION_DAYS: int = 7

    # Optional order pickup window (local time). Set both to enable.
    ORDER_WINDOW_START_HOUR: int | None = None
    ORDER_WINDOW_END_HOUR: int | None = None

    # Menu image uploads
    MENU_IMAGE_UPLOAD_DIR: str = "static/uploads/menu"
    MENU_IMAGE_MAX_BYTES: int = 3 * 1024 * 1024
    MENU_IMAGE_MAX_WIDTH: int = 2500
    MENU_IMAGE_MAX_HEIGHT: int = 2500

    # Profile image uploads
    PROFILE_IMAGE_UPLOAD_DIR: str = "static/uploads/profiles"
    PROFILE_IMAGE_MAX_BYTES: int = 3 * 1024 * 1024
    PROFILE_IMAGE_MAX_WIDTH: int = 2500
    PROFILE_IMAGE_MAX_HEIGHT: int = 2500

    # Default tenant context
    DEFAULT_ORGANIZATION_NAME: str = "Default Organization"

    # Bootstrapped owner account (optional)
    OWNER_EMAIL: str | None = None
    OWNER_PASSWORD: str | None = None
    OWNER_FIRST_NAME: str = "Owner"
    OWNER_LAST_NAME: str = "Account"
    OWNER_ORGANIZATION_NAME: str | None = None
    # Backward-compatible aliases
    OWNER_SEED_EMAIL: str | None = None
    OWNER_SEED_PASSWORD: str | None = None
    OWNER_SEED_FIRST_NAME: str | None = None
    OWNER_SEED_LAST_NAME: str | None = None

    # ISSP SRCE API integration (for student card data)
    # Get credentials from ISSP SRCE: https://isspapi.issp.srce.hr
    ISSP_CLIENT_ID: str | None = None
    ISSP_CLIENT_SECRET: str | None = None
    ISSP_API_BASE_URL: str | None = None  # Defaults to https://isspapi.issp.srce.hr/api

    @field_validator(
        "ORDER_WINDOW_START_HOUR",
        "ORDER_WINDOW_END_HOUR",
        "REDIS_URL",
        "LOG_FILE_PATH",
        "OWNER_SEED_EMAIL",
        "OWNER_SEED_PASSWORD",
        "OWNER_EMAIL",
        "OWNER_PASSWORD",
        "OWNER_ORGANIZATION_NAME",
        "ISSP_CLIENT_ID",
        "ISSP_CLIENT_SECRET",
        "ISSP_API_BASE_URL",
        mode="before",
    )
    @classmethod
    def empty_string_to_none(cls, v):
        if v == "":
            return None
        return v

    @field_validator("ACCESS_TOKEN_EXPIRE_MINUTES")
    @classmethod
    def token_expiry_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("ACCESS_TOKEN_EXPIRE_MINUTES mora biti veci od 0")
        return v

    @field_validator("SECRET_KEY")
    @classmethod
    def secret_key_not_empty(cls, v: str) -> str:
        value = v.strip()
        if not value:
            raise ValueError("SECRET_KEY ne smije biti prazan")
        if value in {
            "change-this-in-production-super-secret-key",
            "replace-with-strong-secret",
        }:
            raise ValueError(
                "SECRET_KEY mora biti stvarna tajna iz okoline, ne placeholder vrijednost"
            )
        if len(value) < 32:
            raise ValueError("SECRET_KEY mora imati najmanje 32 znaka")
        return value

    @field_validator("DEFAULT_ORGANIZATION_NAME")
    @classmethod
    def default_org_name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("DEFAULT_ORGANIZATION_NAME ne smije biti prazan")
        return v.strip()

    @field_validator("ALGORITHM")
    @classmethod
    def algorithm_supported(cls, v: str) -> str:
        allowed = {"HS256"}
        if v not in allowed:
            raise ValueError(f"Nepodrzani ALGORITHM: {v}")
        return v

    @field_validator("ENVIRONMENT")
    @classmethod
    def environment_allowed(cls, v: str) -> str:
        allowed = {"development", "production", "test"}
        if v not in allowed:
            raise ValueError("ENVIRONMENT mora biti development, test ili production")
        return v

    @field_validator("RATE_LIMITER_BACKEND")
    @classmethod
    def rate_limiter_backend_allowed(cls, v: str) -> str:
        allowed = {"memory", "redis"}
        if v not in allowed:
            raise ValueError("RATE_LIMITER_BACKEND mora biti memory ili redis")
        return v

    @field_validator("LOG_ROTATION")
    @classmethod
    def log_rotation_allowed(cls, v: str) -> str:
        allowed = {"size", "time"}
        if v not in allowed:
            raise ValueError("LOG_ROTATION mora biti size ili time")
        return v

    @field_validator("LOGIN_RATE_LIMIT_MAX", "LOGIN_RATE_LIMIT_WINDOW_SECONDS")
    @classmethod
    def rate_limit_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Rate limit vrijednosti moraju biti vece od 0")
        return v

    @field_validator(
        "LOG_FILE_MAX_BYTES",
        "LOG_FILE_BACKUP_COUNT",
        "LOG_RETENTION_DAYS",
        "MENU_IMAGE_MAX_BYTES",
        "MENU_IMAGE_MAX_WIDTH",
        "MENU_IMAGE_MAX_HEIGHT",
        "PROFILE_IMAGE_MAX_BYTES",
        "PROFILE_IMAGE_MAX_WIDTH",
        "PROFILE_IMAGE_MAX_HEIGHT",
    )
    @classmethod
    def logging_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("Logging vrijednosti moraju biti vece od 0")
        return v

    @model_validator(mode="after")
    def normalize_owner_aliases(self):
        if not self.OWNER_EMAIL and self.OWNER_SEED_EMAIL:
            self.OWNER_EMAIL = self.OWNER_SEED_EMAIL
        if not self.OWNER_PASSWORD and self.OWNER_SEED_PASSWORD:
            self.OWNER_PASSWORD = self.OWNER_SEED_PASSWORD
        if self.OWNER_SEED_FIRST_NAME and self.OWNER_FIRST_NAME == "Owner":
            self.OWNER_FIRST_NAME = self.OWNER_SEED_FIRST_NAME
        if self.OWNER_SEED_LAST_NAME and self.OWNER_LAST_NAME == "Account":
            self.OWNER_LAST_NAME = self.OWNER_SEED_LAST_NAME
        if not self.OWNER_ORGANIZATION_NAME:
            self.OWNER_ORGANIZATION_NAME = self.DEFAULT_ORGANIZATION_NAME
        return self

    @model_validator(mode="after")
    def production_constraints(self):
        if self.RATE_LIMITER_BACKEND == "redis" and not self.REDIS_URL:
            raise ValueError("REDIS_URL je obavezan kad je RATE_LIMITER_BACKEND=redis")
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
