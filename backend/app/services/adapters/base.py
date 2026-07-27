from abc import ABC, abstractmethod
from uuid import UUID

from httpx import ConnectError
from pydantic import BaseModel

from app.models.account import Account


class ChatResult(BaseModel):
    content: str
    model: str
    tokens_in: int | None = None
    tokens_out: int | None = None
    account_id: UUID


class ProviderError(Exception):
    def __init__(self, message: str, is_rate_limit: bool = False, is_credit_exhausted: bool = False):
        self.is_rate_limit = is_rate_limit
        self.is_credit_exhausted = is_credit_exhausted
        super().__init__(message)


def classify_error(status_code: int | None, body: str) -> ProviderError:
    body_lower = body.lower()

    if status_code == 429:
        return ProviderError("Rate limit exceeded", is_rate_limit=True)

    if status_code == 402:
        return ProviderError("Insufficient credits", is_credit_exhausted=True)

    if status_code == 403:
        if any(kw in body_lower for kw in ["credit", "quota", "billing"]):
            return ProviderError("Insufficient credits", is_credit_exhausted=True)

    if status_code and status_code >= 400:
        if "insufficient credits" in body_lower:
            return ProviderError("Insufficient credits", is_credit_exhausted=True)
        if "rate limit" in body_lower or "too many requests" in body_lower:
            return ProviderError("Rate limit exceeded", is_rate_limit=True)

    return ProviderError(f"HTTP {status_code}: {body[:200]}")


def classify_connection_error(exc: ConnectError) -> ProviderError:
    return ProviderError(f"Connection error: {exc}")


class BaseProviderAdapter(ABC):
    @abstractmethod
    async def chat_completion(
        self, account: Account, model: str, messages: list, **kwargs
    ) -> ChatResult: ...

    @abstractmethod
    async def check_credits(self, account: Account) -> float | None: ...
