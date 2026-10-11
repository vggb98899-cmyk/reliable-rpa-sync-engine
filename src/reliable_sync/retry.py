from __future__ import annotations

from collections.abc import Callable, Iterable
import time
from typing import TypeVar

T = TypeVar("T")


class ReadRetryExhausted(RuntimeError):
    pass


def retry_read(
    operation: Callable[[], T],
    *,
    attempts: int = 3,
    backoff_seconds: Iterable[float] = (0.01, 0.02),
    retryable: tuple[type[BaseException], ...] = (TimeoutError, ConnectionError),
) -> T:
    """Retry only side-effect-free reads; callers must never wrap writes with this."""
    delays = list(backoff_seconds)
    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except retryable as exc:
            if attempt == attempts:
                raise ReadRetryExhausted(str(exc)) from exc
            delay = delays[min(attempt - 1, len(delays) - 1)] if delays else 0
            time.sleep(delay)
    raise AssertionError("unreachable")
