from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import httpx
import pytest

from app.models.account import Account
from app.models.provider import Provider
from app.services.adapters.base import (
    ChatResult,
    ProviderError,
    classify_connection_error,
    classify_error,
)
from app.services.adapters.nvidia import NVIDIAAdapter
from app.services.adapters.ollama import OllamaAdapter
from app.services.adapters.openrouter import OpenRouterAdapter
from tests.conftest import FakeResponse


# ---------------------------------------------------------------------------
# classify_error
# ---------------------------------------------------------------------------

class TestClassifyError:
    def test_429_is_rate_limit(self):
        err = classify_error(429, "rate limit exceeded")
        assert err.is_rate_limit is True
        assert err.is_credit_exhausted is False

    def test_402_is_credit_exhausted(self):
        err = classify_error(402, "payment required")
        assert err.is_credit_exhausted is True
        assert err.is_rate_limit is False

    @pytest.mark.parametrize("keyword", ["credit", "quota", "billing"])
    def test_403_with_credit_keywords(self, keyword):
        err = classify_error(403, f"insufficient {keyword}")
        assert err.is_credit_exhausted is True
        assert err.is_rate_limit is False

    def test_403_without_keywords(self):
        err = classify_error(403, "forbidden")
        assert err.is_credit_exhausted is False
        assert err.is_rate_limit is False

    def test_4xx_insufficient_credits(self):
        err = classify_error(400, "Insufficient credits for this request")
        assert err.is_credit_exhausted is True

    def test_4xx_rate_limit_keywords(self):
        err = classify_error(429, "Rate limit exceeded")
        assert err.is_rate_limit is True

    def test_unknown_error(self):
        err = classify_error(500, "internal server error")
        assert err.is_credit_exhausted is False
        assert err.is_rate_limit is False

    def test_none_status(self):
        err = classify_error(None, "something went wrong")
        assert err.is_credit_exhausted is False
        assert err.is_rate_limit is False


class TestClassifyConnectionError:
    def test_returns_provider_error_with_no_flags(self):
        exc = httpx.ConnectError("connection refused")
        err = classify_connection_error(exc)
        assert err.is_credit_exhausted is False
        assert err.is_rate_limit is False
        assert "connection" in str(err).lower()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_account(provider: Provider | None = None, api_token: str = "tok") -> Account:
    return Account(
        id=uuid4(),
        provider_id=provider.id if provider else uuid4(),
        api_token=api_token,
        is_active=True,
        is_depleted=False,
        provider=provider,
    )


def _make_provider(name: str = "test", base_url: str | None = "https://api.test.com/v1") -> Provider:
    return Provider(id=uuid4(), name=name, display_name=name.title(), base_url=base_url)


# ---------------------------------------------------------------------------
# OpenRouterAdapter
# ---------------------------------------------------------------------------

class TestOpenRouterAdapter:
    @patch("app.services.adapters.openrouter.httpx.AsyncClient")
    async def test_chat_completion_success(self, mock_client_cls):
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        mock_client.post.return_value = FakeResponse(
            200,
            {
                "choices": [{"message": {"content": "Hello"}}],
                "model": "openai/gpt-4o",
                "usage": {"prompt_tokens": 10, "completion_tokens": 20},
            },
        )

        adapter = OpenRouterAdapter()
        provider = _make_provider(name="openrouter")
        account = _make_account(provider=provider)
        result = await adapter.chat_completion(
            account, "openai/gpt-4o", [{"role": "user", "content": "Hi"}]
        )

        assert isinstance(result, ChatResult)
        assert result.content == "Hello"
        assert result.model == "openai/gpt-4o"
        assert result.tokens_in == 10
        assert result.tokens_out == 20
        assert result.account_id == account.id

        call_kwargs = mock_client.post.call_args[1]
        assert call_kwargs["headers"]["Authorization"] == "Bearer tok"
        assert call_kwargs["headers"]["X-Title"] == "MCP Account Rotation"

    @patch("app.services.adapters.openrouter.httpx.AsyncClient")
    async def test_chat_completion_rate_limit(self, mock_client_cls):
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        mock_client.post.return_value = FakeResponse(429, text="Rate limit exceeded")

        adapter = OpenRouterAdapter()
        account = _make_account()
        with pytest.raises(ProviderError) as exc:
            await adapter.chat_completion(account, "gpt-4o", [{"role": "user", "content": "Hi"}])
        assert exc.value.is_rate_limit is True

    @patch("app.services.adapters.openrouter.httpx.AsyncClient")
    async def test_chat_completion_credit_exhausted(self, mock_client_cls):
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        mock_client.post.return_value = FakeResponse(402, text="Insufficient credits")

        adapter = OpenRouterAdapter()
        account = _make_account()
        with pytest.raises(ProviderError) as exc:
            await adapter.chat_completion(account, "gpt-4o", [{"role": "user", "content": "Hi"}])
        assert exc.value.is_credit_exhausted is True

    @patch("app.services.adapters.openrouter.httpx.AsyncClient")
    async def test_chat_completion_connection_error(self, mock_client_cls):
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        mock_client.post.side_effect = httpx.ConnectError("connection refused")

        adapter = OpenRouterAdapter()
        account = _make_account()
        with pytest.raises(ProviderError) as exc:
            await adapter.chat_completion(account, "gpt-4o", [{"role": "user", "content": "Hi"}])
        assert exc.value.is_rate_limit is False
        assert exc.value.is_credit_exhausted is False

    @patch("app.services.adapters.openrouter.httpx.AsyncClient")
    async def test_check_credits_success(self, mock_client_cls):
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        mock_client.get.return_value = FakeResponse(200, {"credits": 42.5})

        adapter = OpenRouterAdapter()
        account = _make_account()
        credits = await adapter.check_credits(account)
        assert credits == 42.5

    @patch("app.services.adapters.openrouter.httpx.AsyncClient")
    async def test_check_credits_api_error(self, mock_client_cls):
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        mock_client.get.side_effect = httpx.HTTPError("api error")

        adapter = OpenRouterAdapter()
        account = _make_account()
        credits = await adapter.check_credits(account)
        assert credits is None


# ---------------------------------------------------------------------------
# NVIDIAAdapter
# ---------------------------------------------------------------------------

class TestNVIDIAAdapter:
    @patch("app.services.adapters.nvidia.httpx.AsyncClient")
    async def test_chat_completion_success(self, mock_client_cls):
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        mock_client.post.return_value = FakeResponse(
            200,
            {
                "choices": [{"message": {"content": "Hello from NVIDIA"}}],
                "model": "nvidia/llama",
                "usage": {"prompt_tokens": 5, "completion_tokens": 15},
            },
        )

        adapter = NVIDIAAdapter()
        account = _make_account()
        result = await adapter.chat_completion(account, "nvidia/llama", [{"role": "user", "content": "Hi"}])

        assert result.content == "Hello from NVIDIA"
        assert result.tokens_in == 5
        assert result.tokens_out == 15

    @patch("app.services.adapters.nvidia.httpx.AsyncClient")
    async def test_check_credits(self, mock_client_cls):
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        mock_client.get.return_value = FakeResponse(200, {"credits": 100.0})

        adapter = NVIDIAAdapter()
        account = _make_account()
        credits = await adapter.check_credits(account)
        assert credits == 100.0

    @patch("app.services.adapters.nvidia.httpx.AsyncClient")
    async def test_check_credits_balance_field(self, mock_client_cls):
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        mock_client.get.return_value = FakeResponse(200, {"balance": 200.0})

        adapter = NVIDIAAdapter()
        account = _make_account()
        credits = await adapter.check_credits(account)
        assert credits == 200.0


# ---------------------------------------------------------------------------
# OllamaAdapter
# ---------------------------------------------------------------------------

class TestOllamaAdapter:
    @patch("app.services.adapters.ollama.httpx.AsyncClient")
    async def test_chat_completion_success(self, mock_client_cls):
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        mock_client.post.return_value = FakeResponse(
            200,
            {"model": "llama3", "message": {"content": "Hello from Ollama"}},
        )

        adapter = OllamaAdapter()
        account = _make_account()
        result = await adapter.chat_completion(
            account, "llama3", [{"role": "user", "content": "Hi"}]
        )

        assert result.content == "Hello from Ollama"
        assert result.model == "llama3"
        assert result.tokens_in is None
        assert result.tokens_out is None

    @patch("app.services.adapters.ollama.httpx.AsyncClient")
    async def test_chat_completion_with_api_key(self, mock_client_cls):
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        mock_client.post.return_value = FakeResponse(
            200,
            {"model": "llama3", "message": {"content": "OK"}},
        )

        adapter = OllamaAdapter()
        provider = _make_provider(base_url="http://custom:11434")
        account = _make_account(provider=provider, api_token="my-key")
        await adapter.chat_completion(account, "llama3", [{"role": "user", "content": "Hi"}])

        call_kwargs = mock_client.post.call_args[1]
        assert call_kwargs["headers"].get("X-API-Key") == "my-key"

    @patch("app.services.adapters.ollama.httpx.AsyncClient")
    async def test_chat_completion_connection_error(self, mock_client_cls):
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        mock_client.post.side_effect = httpx.ConnectError("refused")

        adapter = OllamaAdapter()
        account = _make_account()
        with pytest.raises(ProviderError) as exc:
            await adapter.chat_completion(account, "llama3", [{"role": "user", "content": "Hi"}])
        assert exc.value.is_rate_limit is False
        assert exc.value.is_credit_exhausted is False

    async def test_check_credits_returns_none(self):
        adapter = OllamaAdapter()
        account = _make_account()
        assert await adapter.check_credits(account) is None

    @patch("app.services.adapters.ollama.httpx.AsyncClient")
    async def test_message_mapping(self, mock_client_cls):
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        mock_client.post.return_value = FakeResponse(
            200,
            {"model": "llama3", "message": {"content": "OK"}},
        )

        adapter = OllamaAdapter()
        account = _make_account()
        messages = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Hi"},
        ]
        await adapter.chat_completion(account, "llama3", messages)

        sent = mock_client.post.call_args[1]["json"]["messages"]
        assert len(sent) == 2
        assert sent[0] == {"role": "system", "content": "You are helpful"}
        assert sent[1] == {"role": "user", "content": "Hi"}


# ---------------------------------------------------------------------------
# Adapter Registry
# ---------------------------------------------------------------------------

class TestAdapterRegistry:
    def test_registry_contains_expected_providers(self):
        from app.services.adapters import ADAPTER_REGISTRY, get_adapter

        assert "openrouter" in ADAPTER_REGISTRY
        assert "nvidia-nim" in ADAPTER_REGISTRY
        assert "ollama" in ADAPTER_REGISTRY

        assert get_adapter("openrouter") is not None
        assert get_adapter("nvidia-nim") is not None
        assert get_adapter("ollama") is not None

    def test_get_adapter_unknown_raises(self):
        from app.services.adapters import get_adapter

        with pytest.raises(ValueError, match="Unknown provider"):
            get_adapter("nonexistent")
