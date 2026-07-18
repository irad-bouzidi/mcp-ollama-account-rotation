import asyncio
from typing import Any

from app.account_manager import AccountManager
from app.client import OllamaClient
from app.config import RetryConfig
from app.exceptions import AllAccountsUnhealthy, OllamaRouterError
from app.logging import get_logger
from app.models import ChatRequest, ChatResponse, GenerateRequest, GenerateResponse, ModelInfo
from app.retry import is_retryable, is_rotation_trigger
from app.storage import StateManager

logger = get_logger(__name__)


class _Metrics:
    def __init__(self) -> None:
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.retries = 0
        self.rotations = 0
        self.per_account: dict[str, dict[str, int]] = {}
        import threading

        self._lock = threading.Lock()

    def record_request(self) -> None:
        with self._lock:
            self.total_requests += 1

    def record_success(self, account_id: str) -> None:
        with self._lock:
            self.successful_requests += 1
            acc = self.per_account.setdefault(account_id, {"requests": 0, "failures": 0, "rotations": 0})
            acc["requests"] += 1

    def record_failure(self, account_id: str) -> None:
        with self._lock:
            self.failed_requests += 1
            acc = self.per_account.setdefault(account_id, {"requests": 0, "failures": 0, "rotations": 0})
            acc["failures"] += 1

    def record_retry(self) -> None:
        with self._lock:
            self.retries += 1

    def record_rotation(self) -> None:
        with self._lock:
            self.rotations += 1

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "total_requests": self.total_requests,
                "successful_requests": self.successful_requests,
                "failed_requests": self.failed_requests,
                "retries": self.retries,
                "rotations": self.rotations,
                "per_account": dict(self.per_account),
            }


metrics = _Metrics()


class Router:
    def __init__(
        self,
        client: OllamaClient,
        account_manager: AccountManager,
        state_manager: StateManager,
        retry_config: RetryConfig,
    ) -> None:
        self._client = client
        self._account_manager = account_manager
        self._state_manager = state_manager
        self._retry_config = retry_config
        self._lock = asyncio.Lock()

    async def chat(self, request: ChatRequest) -> ChatResponse:
        result = await self._execute_with_rotation("chat", request)
        assert isinstance(result, ChatResponse)
        return result

    async def generate(self, request: GenerateRequest) -> GenerateResponse:
        result = await self._execute_with_rotation("generate", request)
        assert isinstance(result, GenerateResponse)
        return result

    async def list_models(self) -> list[ModelInfo]:
        result = await self._execute_with_rotation("list_models")
        assert isinstance(result, list)
        return result

    async def _execute_with_rotation(self, method_name: str, request: Any = None, **kwargs: Any) -> Any:
        metrics.record_request()
        async with self._lock:
            max_attempts = self._retry_config.max_attempts
            for attempt in range(max_attempts):
                account = self._account_manager.get_active()
                if account is None:
                    account = self._account_manager.rotate()
                if account is None:
                    raise AllAccountsUnhealthy("No healthy accounts available")

                logger.info("account_selected", account_id=account.id)
                api_key = account.api_key.get_secret_value()

                try:
                    result: Any = None
                    if method_name == "chat":
                        assert request is not None
                        result = await self._client.chat(request, api_key)
                    elif method_name == "generate":
                        assert request is not None
                        result = await self._client.generate(request, api_key)
                    elif method_name == "list_models":
                        result = await self._client.list_models(api_key)
                    else:
                        raise ValueError(f"Unknown method: {method_name}")

                    self._state_manager.record_success(account.id)
                    self._account_manager.mark_healthy(account.id)
                    metrics.record_success(account.id)
                    return result

                except OllamaRouterError as e:
                    logger.warning("request_failed", account_id=account.id, error=str(e), attempt=attempt)
                    self._state_manager.record_failure(account.id, str(e))
                    self._account_manager.mark_unhealthy(account.id)
                    metrics.record_failure(account.id)

                    if is_rotation_trigger(e):
                        self._account_manager.rotate()
                        metrics.record_rotation()
                        logger.info("account_rotated", reason=str(e))

                    can_retry = is_retryable(e) or is_rotation_trigger(e)
                    if can_retry and attempt < max_attempts - 1:
                        metrics.record_retry()
                        logger.info("retry_attempt", attempt=attempt + 1, max_attempts=max_attempts)
                        continue

                    if not can_retry:
                        raise

            raise AllAccountsUnhealthy("Exhausted all retry attempts")
