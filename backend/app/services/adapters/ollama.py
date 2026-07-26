import httpx

from app.models.account import Account
from app.services.adapters.base import (
    BaseProviderAdapter,
    ChatResult,
    ProviderError,
    classify_connection_error,
)

DEFAULT_BASE_URL = "http://host.docker.internal:11434"


class OllamaAdapter(BaseProviderAdapter):
    async def chat_completion(
        self, account: Account, model: str, messages: list, **kwargs
    ) -> ChatResult:
        base_url = (
            account.provider.base_url
            if account.provider and account.provider.base_url
            else DEFAULT_BASE_URL
        )
        url = f"{base_url.rstrip('/')}/api/chat"

        headers = {"Content-Type": "application/json"}
        if account.api_token:
            headers["X-API-Key"] = account.api_token

        ollama_messages = [_map_message(m) for m in messages]

        payload = {
            "model": model,
            "messages": ollama_messages,
            "stream": False,
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(url, json=payload, headers=headers)

            if resp.status_code >= 400:
                raise ProviderError(
                    f"Ollama API error (HTTP {resp.status_code}): {resp.text[:200]}"
                )

            data = resp.json()
            content = data.get("message", {}).get("content", "")

            return ChatResult(
                content=content,
                model=data.get("model", model),
                tokens_in=None,
                tokens_out=None,
                account_id=account.id,
            )

        except httpx.ConnectError as e:
            raise classify_connection_error(e)
        except httpx.TimeoutException as e:
            raise ProviderError(f"Request timed out: {e}")

    async def check_credits(self, account: Account) -> float | None:
        return None


def _map_message(message: dict) -> dict:
    return {
        "role": message.get("role", "user"),
        "content": message.get("content", ""),
    }
