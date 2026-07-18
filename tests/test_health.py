import anyio
import pytest
import respx

from app.config import HealthConfig
from app.health import HealthChecker


@pytest.mark.asyncio
async def test_probe_success_recovery(ollama_client, account_manager, state_manager):
    account_manager.mark_unhealthy("acc-1")
    assert account_manager.is_healthy("acc-1") is False

    config = HealthConfig(interval_seconds=1, timeout_seconds=5)
    checker = HealthChecker(ollama_client, account_manager, state_manager, config)

    with respx.mock(base_url="https://api.ollama.com") as mock:
        mock.get("/api/tags").respond(json={"models": [{"name": "llama3"}]})
        healthy = await checker._probe(account_manager.get_all()[0])
        assert healthy is True

    account_manager.mark_healthy("acc-1")
    assert account_manager.is_healthy("acc-1") is True


@pytest.mark.asyncio
async def test_probe_failure(ollama_client, account_manager, state_manager):
    account_manager.mark_unhealthy("acc-1")

    config = HealthConfig(interval_seconds=1, timeout_seconds=5)
    checker = HealthChecker(ollama_client, account_manager, state_manager, config)

    with respx.mock(base_url="https://api.ollama.com") as mock:
        mock.get("/api/tags").respond(500)
        healthy = await checker._probe(account_manager.get_all()[0])
        assert healthy is False


@pytest.mark.asyncio
async def test_stop_start(ollama_client, account_manager, state_manager):
    config = HealthConfig(interval_seconds=1, timeout_seconds=5)
    checker = HealthChecker(ollama_client, account_manager, state_manager, config)
    await checker.start()
    await anyio.sleep(0.1)
    await checker.stop()
