"""Redis client helpers for optional distributed caching support."""

from __future__ import annotations

import logging
import os
import time

try:  # pragma: no cover - optional dependency branch
    from redis import Redis
    from redis.exceptions import RedisError
except ModuleNotFoundError:  # pragma: no cover - testing environments without redis
    Redis = None  # type: ignore[assignment]

    class RedisError(Exception):
        """Fallback error type when redis-py is unavailable."""

        pass

logger = logging.getLogger(__name__)

DEFAULT_REDIS_URL = "redis://redis:6379/0"


def create_redis_client(
    url: str | None = None,
    *,
    max_retries: int = 3,
    retry_interval_s: float = 0.5,
) -> Redis | None:
    """Initialise a Redis client if configuration is available.

    Parameters
    ----------
    url:
        Optional Redis connection URL. If omitted, the ``REDIS_URL`` environment
        variable is consulted. When neither is present a ``None`` client is
        returned so callers can fall back to in-memory behaviour.
    max_retries:
        Number of connection attempts before giving up.
    retry_interval_s:
        Delay between connection attempts in seconds.
    """

    if Redis is None:
        logger.info("redis-py not installed; using in-memory services")
        return None

    redis_url = url or os.getenv("REDIS_URL", DEFAULT_REDIS_URL)
    if not redis_url:
        return None

    client = Redis.from_url(redis_url, decode_responses=False)
    for attempt in range(1, max_retries + 1):
        try:
            client.ping()
            logger.info("Connected to Redis at %s", redis_url)
            return client
        except RedisError as exc:  # pragma: no cover - network failure path
            logger.warning(
                "Redis connection attempt %s/%s failed: %s", attempt, max_retries, exc
            )
            time.sleep(retry_interval_s)
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Unexpected error connecting to Redis: %s", exc)
            break

    logger.warning("Redis unavailable at %s; continuing with in-memory services", redis_url)
    return None


def close_redis_client(client: Redis | None) -> None:
    """Close the provided Redis client, ignoring errors."""

    if client is None or Redis is None:
        return
    try:
        client.close()
    except (RedisError, OSError):  # pragma: no cover - defensive cleanup
        logger.debug("Failed to close Redis client", exc_info=True)
