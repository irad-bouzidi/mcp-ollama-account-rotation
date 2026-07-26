# Step 4: Provider Adapters & Rotation Service

## Goal

Build the provider adapter interface, implement adapters for Ollama, OpenRouter, and NVIDIA NIM, then build the rotation service that handles auto-failover.

---

## Tasks

### 4.1 Base Adapter Interface

**`backend/app/services/adapters/base.py`**

```python
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

class BaseProviderAdapter(ABC):
    @abstractmethod
    async def chat_completion(
        self, account: Account, model: str, messages: list, **kwargs
    ) -> ChatResult: ...

    @abstractmethod
    async def check_credits(self, account: Account) -> float | None: ...
```

### 4.2 Provider Adapters

**`backend/app/services/adapters/openrouter.py`**

- OpenAI-compatible API at configured `base_url`
- Auth: `Authorization: Bearer {api_token}`
- Headers: `X-Title: MCP Account Rotation`
- Credit detection: parse 429/402 responses and error body for:
  - `"Insufficient credits"`, `"quota exceeded"`, `"rate limit"`
  - Maps to `ProviderError(is_credit_exhausted=True)` or `ProviderError(is_rate_limit=True)`
- `check_credits`: calls `GET /api/v1/auth/key` (or relevant endpoint) to check remaining credits

**`backend/app/services/adapters/nvidia.py`**

- OpenAI-compatible API at `https://integrate.api.nvidia.com/v1`
- Auth: `Authorization: Bearer {api_token}`
- Credit detection: 402 Payment Required, error body credit keywords
- `check_credits`: calls user/credits endpoint if available

**`backend/app/services/adapters/ollama.py`**

- API at configured `base_url` (default: `http://host.docker.internal:11434`)
- Uses `/api/chat` endpoint with Ollama JSON format
- Maps messages from OpenAI format to Ollama format internally
- Auth: typically none (local). Supports `X-API-Key` header if configured.
- Credit detection: not applicable (local). Connection errors → `ProviderError(is_rate_limit=False)`
- `check_credits`: returns `None` (no credit tracking for local)

### 4.3 Adapter Registry

**`backend/app/services/adapters/__init__.py`**

```python
ADAPTER_REGISTRY: dict[str, type[BaseProviderAdapter]] = {
    "openrouter": OpenRouterAdapter,
    "nvidia-nim": NVIDIAAdapter,
    "ollama": OllamaAdapter,
}

def get_adapter(provider_name: str) -> BaseProviderAdapter:
    cls = ADAPTER_REGISTRY.get(provider_name)
    if not cls:
        raise ValueError(f"Unknown provider: {provider_name}")
    return cls()
```

### 4.4 Rotation Service

**`backend/app/services/rotation.py`**

```python
class RotationService:
    def __init__(self, db: AsyncSession): ...

    async def chat_completion(
        self, provider_name: str, model: str, messages: list, **kwargs
    ) -> ChatResult:
        """
        Core method:
        1. Get provider by name
        2. Get all active, non-depleted accounts
        3. Iterate through accounts, trying each one
        4. On credit/rate-limit error: mark depleted, try next
        5. On success: return result
        6. If all exhausted: raise AllAccountsExhausted
        """
        ...
```

**Detailed flow:**
```python
async def chat_completion(self, provider_name, model, messages, **kwargs):
    # 1. Resolve provider
    provider = await self._get_provider(provider_name)
    adapter = get_adapter(provider.name)

    # 2. Get candidate accounts (active & not depleted)
    accounts = await self._get_available_accounts(provider.id)
    if not accounts:
        raise NoAvailableAccounts(provider_name)

    errors = []
    for account in accounts:
        try:
            result = await adapter.chat_completion(account, model, messages, **kwargs)
            # Log success
            await self._log_usage(account.id, provider.id, model, result, success=True)
            await self._increment_requests(account.id)
            return result

        except ProviderError as e:
            await self._log_usage(account.id, provider.id, model, None, success=False, error=str(e))
            errors.append(str(e))

            if e.is_credit_exhausted or e.is_rate_limit:
                await self._mark_depleted(account.id, str(e))
                continue  # try next account
            else:
                # Non-credit error (e.g., bad request, invalid model) — don't mark depleted
                # but don't retry either; let the caller know
                raise

    # All accounts exhausted
    available_providers = await self._get_available_providers()
    raise AllAccountsExhausted(
        f"All {len(accounts)} accounts for {provider_name} are depleted. "
        f"Available providers: {available_providers}. Consider switching."
    )
```

**Additional methods:**
```python
    async def get_active_account(self, provider_name: str) -> Account | None:
        """Returns first active, non-depleted account for the provider."""
        ...

    async def switch_account(self, provider_name: str) -> Account:
        """Manually rotate to the next available account."""
        ...

    async def reset_account(self, account_id: UUID) -> Account:
        """Reset is_depleted flag (e.g., after billing cycle)."""
        ...
```

### 4.5 Error Types

```python
class AllAccountsExhausted(Exception):
    """All accounts for a provider are depleted."""

class NoAvailableAccounts(Exception):
    """No active, non-depleted accounts for the provider."""

class ProviderNotFound(Exception):
    """Unknown provider name."""
```

## Error Classification

The adapter's `ProviderError` must correctly classify the error:

| HTTP Status | Error Body Keywords | Classification |
|---|---|---|
| 429 | any | `is_rate_limit=True` |
| 402 | any | `is_credit_exhausted=True` |
| 403 | "credit", "quota", "billing" | `is_credit_exhausted=True` |
| 4xx/5xx | "insufficient credits" | `is_credit_exhausted=True` |
| 4xx/5xx | "rate limit", "too many requests" | `is_rate_limit=True` |
| Connection error | timeout, refused | Neither (transient, don't mark depleted) |

## Verification

```python
# Python test
from app.services.rotation import RotationService

async def test():
    svc = RotationService(db)
    result = await svc.chat_completion(
        provider_name="openrouter",
        model="openai/gpt-4o",
        messages=[{"role": "user", "content": "Hello"}]
    )
    print(result.content)
```

## Files to create

- `backend/app/services/__init__.py`
- `backend/app/services/adapters/__init__.py`
- `backend/app/services/adapters/base.py`
- `backend/app/services/adapters/openrouter.py`
- `backend/app/services/adapters/nvidia.py`
- `backend/app/services/adapters/ollama.py`
- `backend/app/services/rotation.py`
