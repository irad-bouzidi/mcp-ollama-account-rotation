# Step 3: REST API (FastAPI)

## Goal

Build the CRUD REST API for providers and accounts, plus a system status endpoint. The React frontend will consume these endpoints.

---

## Endpoints

### Providers

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/providers` | List all providers with account counts |
| `GET` | `/api/providers/{id}` | Get provider by ID |
| `POST` | `/api/providers` | Create a new provider |
| `PUT` | `/api/providers/{id}` | Update a provider |
| `DELETE` | `/api/providers/{id}` | Delete a provider and its accounts |

### Accounts

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/accounts` | List all accounts (filterable by `provider_id`) |
| `GET` | `/api/accounts/{id}` | Get account by ID |
| `POST` | `/api/accounts` | Create a new account |
| `PUT` | `/api/accounts/{id}` | Update an account |
| `DELETE` | `/api/accounts/{id}` | Delete an account |
| `POST` | `/api/accounts/{id}/toggle` | Toggle `is_active` |
| `POST` | `/api/accounts/{id}/reset` | Reset `is_depleted` flag |

### System

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/status` | Full system health: provider status, account counts, depletion alerts |
| `GET` | `/api/usage` | Recent usage logs (paginated, filterable) |

---

## Pydantic Schemas

**`backend/app/schemas/provider.py`**
```python
class ProviderBase(BaseModel):
    name: str
    display_name: str | None = None
    base_url: str | None = None

class ProviderCreate(ProviderBase): ...
class ProviderUpdate(BaseModel):
    display_name: str | None = None
    base_url: str | None = None

class ProviderRead(ProviderBase):
    id: UUID
    created_at: datetime
    account_count: int = 0
    active_accounts: int = 0
    depleted_accounts: int = 0
```

**`backend/app/schemas/account.py`**
```python
class AccountBase(BaseModel):
    provider_id: UUID
    email: str | None = None
    api_token: str

class AccountCreate(AccountBase): ...
class AccountUpdate(BaseModel):
    email: str | None = None
    api_token: str | None = None
    is_active: bool | None = None

class AccountRead(BaseModel):
    id: UUID
    provider_id: UUID
    email: str | None
    is_active: bool
    is_depleted: bool
    credits_remaining: Decimal | None
    last_error: str | None
    requests_count: int
    rate_limit_reset: datetime | None
    created_at: datetime
    # api_token is NEVER returned in responses
```

**`backend/app/schemas/status.py`**
```python
class ProviderStatus(BaseModel):
    id: UUID
    name: str
    display_name: str | None
    total_accounts: int
    active_accounts: int
    depleted_accounts: int
    has_available: bool  # at least one non-depleted active account
    current_active_account: AccountRead | None

class SystemStatus(BaseModel):
    providers: list[ProviderStatus]
    any_available: bool  # any provider has an available account
    depleted_providers: list[str]  # providers with all accounts depleted
```

---

## Implementation Details

### Routers

Each router file uses `APIRouter(prefix="/api/...", tags=[...])`.

### Dependencies

- `get_db()` from `database.py` — yields async session
- `get_settings()` from `config.py` — yields app settings

### Response Handling

- All endpoints return Pydantic models (FastAPI auto-serializes)
- 404 for not-found resources
- 409 for unique constraint violations (duplicate provider name)
- 422 for validation errors (automatic from Pydantic)

### Key Logic

**`GET /api/providers`** — For each provider, attach:
- `account_count`: total accounts
- `active_accounts`: count where `is_active=True`
- `depleted_accounts`: count where `is_depleted=True`

**`POST /api/accounts`** — Validate that `provider_id` exists before creating.

**`GET /api/status`** — Aggregate across all providers:
- Which providers have available (non-depleted, active) accounts
- Which providers are fully depleted
- Current active account per provider (first non-depleted active account)

### CORS

In `main.py`, configure CORS middleware to allow the frontend origin:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:80"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Verification

```bash
# Create a provider
curl -X POST http://localhost:8000/api/providers \
  -H "Content-Type: application/json" \
  -d '{"name": "openrouter", "display_name": "OpenRouter", "base_url": "https://openrouter.ai/api/v1"}'

# List providers
curl http://localhost:8000/api/providers

# Create an account
curl -X POST http://localhost:8000/api/accounts \
  -H "Content-Type: application/json" \
  -d '{"provider_id": "...", "email": "user@example.com", "api_token": "sk-..."}'

# Get system status
curl http://localhost:8000/api/status
```

## Files to create

- `backend/app/schemas/__init__.py`
- `backend/app/schemas/provider.py`
- `backend/app/schemas/account.py`
- `backend/app/schemas/status.py`
- `backend/app/routers/__init__.py`
- `backend/app/routers/providers.py`
- `backend/app/routers/accounts.py`
- `backend/app/routers/usage.py`
