import random
import time
from collections.abc import Callable
from functools import wraps
from typing import TypeVar

from app.config import RetryConfig
from app.exceptions import (
    AccountDisabled,
    AuthenticationFailed,
    NetworkFailure,
    OllamaRouterError,
    QuotaExceeded,
    RateLimited,
    ServerError,
)

F = TypeVar("F", bound=Callable[..., object])


def is_retryable(exc: OllamaRouterError) -> bool:
    return isinstance(exc, (RateLimited, ServerError, NetworkFailure))


def is_rotation_trigger(exc: OllamaRouterError) -> bool:
    return isinstance(exc, (QuotaExceeded, AuthenticationFailed, AccountDisabled, RateLimited, ServerError))


def retry_with_backoff(config: RetryConfig) -> Callable[[F], F]:
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: object, **kwargs: object) -> object:
            last_exc: OllamaRouterError | None = None
            for attempt in range(config.max_attempts):
                try:
                    return func(*args, **kwargs)
                except OllamaRouterError as e:
                    if not is_retryable(e):
                        raise
                    last_exc = e
                    if attempt == config.max_attempts - 1:
                        raise
                    delay = min(config.backoff_base**attempt, config.backoff_max)
                    jitter = random.uniform(0, config.jitter * delay)
                    time.sleep(delay + jitter)  # noqa: ASYNC251 - sync retry wrapper
            raise last_exc  # type: ignore[misc]

        return wrapper  # type: ignore[return-value]

    return decorator


class RoundRobinRotation:
    def __init__(self) -> None:
        self._index = 0

    def next(self, account_ids: list[str], healthy_filter: Callable[[str], bool]) -> str | None:
        if not account_ids:
            return None
        healthy = [aid for aid in account_ids if healthy_filter(aid)]
        if not healthy:
            return None
        if self._index >= len(healthy):
            self._index = 0
        result = healthy[self._index]
        self._index = (self._index + 1) % len(healthy)
        return result
