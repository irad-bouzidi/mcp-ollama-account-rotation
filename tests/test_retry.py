import pytest

from app.config import RetryConfig
from app.exceptions import AuthenticationFailed, NetworkFailure, RateLimited, ServerError
from app.retry import is_retryable, is_rotation_trigger, retry_with_backoff


def test_is_retryable():
    assert is_retryable(RateLimited("too fast")) is True
    assert is_retryable(ServerError("500")) is True
    assert is_retryable(NetworkFailure("connection")) is True
    assert is_retryable(AuthenticationFailed("bad key")) is False


def test_is_rotation_trigger():
    assert is_rotation_trigger(RateLimited("too fast")) is True
    assert is_rotation_trigger(ServerError("500")) is True
    assert is_rotation_trigger(AuthenticationFailed("bad key")) is True
    assert is_rotation_trigger(NetworkFailure("connection")) is False


def test_retry_decorator_success():
    config = RetryConfig(max_attempts=3)
    call_count = 0

    @retry_with_backoff(config)
    def fn():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise NetworkFailure("transient")
        return "ok"

    result = fn()
    assert result == "ok"
    assert call_count == 2


def test_retry_decorator_exhausted():
    config = RetryConfig(max_attempts=2)
    call_count = 0

    @retry_with_backoff(config)
    def fn():
        nonlocal call_count
        call_count += 1
        raise NetworkFailure("persistent")

    with pytest.raises(NetworkFailure):
        fn()
    assert call_count == 2


def test_non_retryable_passthrough():
    config = RetryConfig(max_attempts=3)

    @retry_with_backoff(config)
    def fn():
        raise AuthenticationFailed("bad key")

    with pytest.raises(AuthenticationFailed):
        fn()
