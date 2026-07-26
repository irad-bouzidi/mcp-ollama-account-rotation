import httpx

from app.models.account import Account
from app.services.adapters.base import (
    BaseProviderAdapter,
    ChatResult,
    ProviderError,
    classify_error,
    classify_connection_error,
)

DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"


class NVIDIAAdapter(BaseProviderAdapter):
    async def chat_completion(
        self, account: Account, model: str, messages: list, **kwargs
    ) -> ChatResult:
        base_url = (
            account.provider.base_url
            if account.provider and account.provider.base_url
            else DEFAULT_BASE_URL
        )
        url = f"{base_url.rstrip('/')}/chat/completions"

        headers = {
            "Authorization": f"Bearer {account.api_token}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model,
            "messages": messages,
            **kwargs,
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(url, json=payload, headers=headers)

            if resp.status_code >= 400:
                raise classify_error(resp.status_code, resp.text)

            data = resp.json()
            choice = data["choices"][0]
            content = choice["message"]["content"]
            usage = data.get("usage", {})

            return ChatResult(
                content=content or "",
                model=data.get("model", model),
                tokens_in=usage.get("prompt_tokens"),
                tokens_out=usage.get("completion_tokens"),
                account_id=account.id,
            )

        except httpx.HTTPStatusError as e:
            raise classify_error(e.response.status_code, e.response.text)
        except httpx.ConnectError as e:
            raise classify_connection_error(e)
        except httpx.TimeoutException as e:
            raise ProviderError(f"Request timed out: {e}")

    async def check_credits(self, account: Account) -> float | None:
        base_url = (
            account.provider.base_url
            if account.provider and account.provider.base_url
            else DEFAULT_BASE_URL
        )
        url = f"{base_url.rstrip('/')}/user/credits"

        headers = {"Authorization": f"Bearer {account.api_token}"}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(url, headers=headers)

            if resp.status_code == 200:
                data = resp.json()
                credits = data.get("credits", data.get("balance"))
                return float(credits) if credits is not None else None
            return None

        except httpx.HTTPError:
            return None
