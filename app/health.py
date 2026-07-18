import asyncio
import time
from typing import Any

from app.account_manager import AccountManager
from app.client import OllamaClient
from app.config import HealthConfig
from app.logging import get_logger
from app.storage import StateManager

logger = get_logger(__name__)


class HealthChecker:
    def __init__(
        self,
        client: OllamaClient,
        account_manager: AccountManager,
        state_manager: StateManager,
        config: HealthConfig,
    ) -> None:
        self._client = client
        self._account_manager = account_manager
        self._state_manager = state_manager
        self._config = config
        self._task: asyncio.Task[None] | None = None
        self._probe_counts: dict[str, int] = {}
        self._probe_intervals: dict[str, float] = {}

    async def start(self) -> None:
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run(self) -> None:
        while True:
            accounts = self._account_manager.get_all()
            for account in accounts:
                if not self._account_manager.is_healthy(account.id):
                    last_probe = self._probe_counts.get(account.id, 0)
                    interval = self._probe_intervals.get(account.id, float(self._config.interval_seconds))
                    if last_probe == 0 or (time.monotonic() - last_probe) >= interval:
                        healthy = await self._probe(account)
                        if healthy:
                            self._account_manager.mark_healthy(account.id)
                            self._state_manager.set_status(account.id, "healthy")
                            self._probe_counts[account.id] = 0
                            self._probe_intervals[account.id] = float(self._config.interval_seconds)
                            logger.info("account_recovered", account_id=account.id)
                        else:
                            self._probe_counts[account.id] = self._probe_counts.get(account.id, 0) + 1
                            backoff = min(
                                float(self._config.interval_seconds) * (2 ** self._probe_counts[account.id]),
                                300.0,
                            )
                            self._probe_intervals[account.id] = backoff
                            logger.debug("probe_failed", account_id=account.id, next_probe=backoff)
            await asyncio.sleep(self._config.interval_seconds)

    async def _probe(self, account: Any) -> bool:
        import time

        start = time.monotonic()
        api_key = account.api_key.get_secret_value()
        try:
            healthy = await self._client.check_health(api_key)
            elapsed = (time.monotonic() - start) * 1000
            if healthy:
                logger.debug("probe_success", account_id=account.id, latency_ms=round(elapsed, 1))
            else:
                logger.debug("probe_failure", account_id=account.id, latency_ms=round(elapsed, 1))
            return healthy
        except Exception as e:
            elapsed = (time.monotonic() - start) * 1000
            logger.debug("probe_error", account_id=account.id, error=str(e), latency_ms=round(elapsed, 1))
            return False
