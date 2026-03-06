"""
Generic async and sync retry utilities with exponential backoff.
Used by services that make external HTTP calls (Spotify, YouTube).
"""
import asyncio
import functools
import time
from typing import Any, Callable, Sequence

from app.core.logging_config import get_logger

logger = get_logger(__name__)


def async_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    backoff_factor: float = 2.0,
    retryable_exceptions: Sequence[type[Exception]] = (Exception,),
) -> Callable:
    """
    Async decorator that retries a coroutine on failure with exponential backoff.

    Args:
        max_attempts: Total number of attempts (including the first one).
        base_delay: Delay in seconds before the first retry.
        backoff_factor: Multiplier applied to delay after each retry.
        retryable_exceptions: Tuple of exception types that trigger a retry.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Exception | None = None
            delay = base_delay

            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except tuple(retryable_exceptions) as exc:
                    last_exception = exc
                    if attempt >= max_attempts:
                        logger.warning(
                            "Retry exhausted for %s after %d attempts: %s",
                            func.__qualname__,
                            max_attempts,
                            exc,
                        )
                        raise
                    logger.info(
                        "Retry %d/%d for %s in %.1fs: %s",
                        attempt,
                        max_attempts,
                        func.__qualname__,
                        delay,
                        exc,
                    )
                    await asyncio.sleep(delay)
                    delay *= backoff_factor

            raise last_exception  # type: ignore[misc]  # unreachable but satisfies type checker

        return wrapper
    return decorator


def sync_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    backoff_factor: float = 2.0,
    retryable_exceptions: Sequence[type[Exception]] = (Exception,),
) -> Callable:
    """
    Sync decorator that retries a function on failure with exponential backoff.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Exception | None = None
            delay = base_delay

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except tuple(retryable_exceptions) as exc:
                    last_exception = exc
                    if attempt >= max_attempts:
                        logger.warning(
                            "Retry exhausted for %s after %d attempts: %s",
                            func.__qualname__,
                            max_attempts,
                            exc,
                        )
                        raise
                    logger.info(
                        "Retry %d/%d for %s in %.1fs: %s",
                        attempt,
                        max_attempts,
                        func.__qualname__,
                        delay,
                        exc,
                    )
                    time.sleep(delay)
                    delay *= backoff_factor

            raise last_exception  # type: ignore[misc]

        return wrapper
    return decorator
