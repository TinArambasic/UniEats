from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from dataclasses import dataclass
from threading import Lock

from redis import Redis
from redis.exceptions import RedisError

from app.config import settings


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    retry_after: int = 0


class RateLimiterUnavailable(RuntimeError):
    pass


class RateLimiter(ABC):
    @abstractmethod
    def configure(self, max_attempts: int, window_seconds: int) -> None:
        raise NotImplementedError

    @abstractmethod
    def check(self, key: str) -> RateLimitResult:
        raise NotImplementedError

    def reset(self) -> None:
        """Optional reset for tests."""
        return None


class InMemoryRateLimiter(RateLimiter):
    def __init__(self, max_attempts: int, window_seconds: int) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def configure(self, max_attempts: int, window_seconds: int) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds

    def check(self, key: str) -> RateLimitResult:
        now = time.time()
        with self._lock:
            events = self._events[key]
            cutoff = now - self.window_seconds
            while events and events[0] < cutoff:
                events.popleft()
            if len(events) >= self.max_attempts:
                oldest = events[0] if events else now
                retry_after = int(max(0, self.window_seconds - (now - oldest)))
                return RateLimitResult(allowed=False, retry_after=retry_after)
            events.append(now)
            return RateLimitResult(allowed=True, retry_after=0)

    def reset(self) -> None:
        with self._lock:
            self._events.clear()


class RedisRateLimiter(RateLimiter):
    """Fixed-window Redis rate limiter using INCR + EXPIRE.

    This is intentionally simple and reliable for login throttling.
    """

    def __init__(
        self,
        client: Redis,
        max_attempts: int,
        window_seconds: int,
        key_prefix: str,
    ) -> None:
        self.client = client
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.key_prefix = key_prefix

    def configure(self, max_attempts: int, window_seconds: int) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds

    def check(self, key: str) -> RateLimitResult:
        try:
            window_id = int(time.time() // self.window_seconds)
            redis_key = f"{self.key_prefix}:{key}:{window_id}"
            count = self.client.incr(redis_key)
            if count == 1:
                self.client.expire(redis_key, self.window_seconds)

            if count > self.max_attempts:
                ttl = self.client.ttl(redis_key)
                retry_after = max(0, ttl if ttl >= 0 else self.window_seconds)
                return RateLimitResult(allowed=False, retry_after=retry_after)
            return RateLimitResult(allowed=True, retry_after=0)
        except RedisError as exc:
            raise RateLimiterUnavailable("Redis nije dostupan") from exc


_rate_limiter_instance: RateLimiter | None = None
_rate_limiter_backend: str | None = None


def _build_rate_limiter() -> RateLimiter:
    backend = settings.RATE_LIMITER_BACKEND
    if backend == "redis":
        if not settings.REDIS_URL:
            raise RateLimiterUnavailable("REDIS_URL nije konfiguriran")
        client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
        return RedisRateLimiter(
            client=client,
            max_attempts=settings.LOGIN_RATE_LIMIT_MAX,
            window_seconds=settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS,
            key_prefix=settings.REDIS_RATE_LIMIT_PREFIX,
        )
    return InMemoryRateLimiter(
        max_attempts=settings.LOGIN_RATE_LIMIT_MAX,
        window_seconds=settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS,
    )


def get_rate_limiter() -> RateLimiter:
    global _rate_limiter_instance, _rate_limiter_backend
    if (
        _rate_limiter_instance is None
        or _rate_limiter_backend != settings.RATE_LIMITER_BACKEND
    ):
        _rate_limiter_instance = _build_rate_limiter()
        _rate_limiter_backend = settings.RATE_LIMITER_BACKEND
    _rate_limiter_instance.configure(
        settings.LOGIN_RATE_LIMIT_MAX,
        settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS,
    )
    return _rate_limiter_instance


def reset_rate_limiter() -> None:
    global _rate_limiter_instance, _rate_limiter_backend
    if _rate_limiter_instance is not None:
        _rate_limiter_instance.reset()
    _rate_limiter_instance = None
    _rate_limiter_backend = None
