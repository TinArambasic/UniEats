from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path
from typing import Any

from app.config import settings

LOGGER_NAME = "unieats"

REDACT_KEYS = {"password", "token", "secret", "access_token"}


def _mask_card_number(value: str) -> str:
    if not value:
        return value
    if len(value) <= 4:
        return "*" * len(value)
    return f"{'*' * (len(value) - 4)}{value[-4:]}"


def _redact_fields(fields: dict[str, Any]) -> dict[str, Any]:
    redacted: dict[str, Any] = {}
    for key, value in fields.items():
        lowered = key.lower()
        if lowered in REDACT_KEYS:
            redacted[key] = "***"
            continue
        if lowered in {"card_number", "student_card_number"} and isinstance(value, str):
            redacted[key] = _mask_card_number(value)
            continue
        redacted[key] = value
    return redacted


def _configure_logger() -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(message)s")

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    if settings.LOG_FILE_PATH:
        log_path = Path(settings.LOG_FILE_PATH)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        if settings.LOG_ROTATION == "time":
            file_handler = TimedRotatingFileHandler(
                log_path,
                when="D",
                interval=1,
                backupCount=settings.LOG_RETENTION_DAYS,
                encoding="utf-8",
            )
        else:
            file_handler = RotatingFileHandler(
                log_path,
                maxBytes=settings.LOG_FILE_MAX_BYTES,
                backupCount=settings.LOG_FILE_BACKUP_COUNT,
                encoding="utf-8",
            )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    logger.propagate = False
    return logger


def log_event(event: str, **fields: Any) -> None:
    logger = _configure_logger()
    payload = {
        "event": event,
        "timestamp": datetime.now(UTC).isoformat(),
        **_redact_fields(fields),
    }
    logger.info(json.dumps(payload, ensure_ascii=False))
