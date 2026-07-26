# AI Provider Account Rotation MCP — Global Plan

## Problem

Multiple API accounts across Ollama, OpenRouter, and NVIDIA NIM need automatic failover when one account hits its rate limit or credit exhaustion. Accounts must be managed via a UI, data persisted in PostgreSQL, and the system must be containerized for one-command deployment.

## Solution

A **Model Context Protocol (MCP) server** in Python that proxies AI chat requests through a pool of provider accounts with automatic rotation on failure. Includes a **React SPA** for account management and **PostgreSQL** for persistence. Containerized via Docker Compose.

---

## Project Root Layout

```
project-root/
├── backend/          ← Python app (FastAPI + FastMCP)
│   ├── app/
│   ├── alembic/
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/         ← React SPA
│   ├── src/
│   ├── Dockerfile
│   ├── package.json
│   └── vite.config.ts
├── docker-compose.yml
├── .env.example
└── doc/              ← This plan
```

All Python code lives under `backend/`. All React/TypeScript code lives under `frontend/`. Each directory has its own `Dockerfile` and dependency management (`requirements.txt` / `package.json`). Docker Compose orchestrates them together.

---

## Architecture

```
AI Assistant (opencode, claude code, etc.)
    │  stdio (local)  or  Streamable HTTP (remote)
    ▼
┌──────────────────────────────────────┐
│  Python Backend (FastAPI + FastMCP)  │
│                                      │
│  ┌──────────────┐  ┌──────────────┐  │
│  │  FastMCP      │  │  FastAPI     │  │
│  │  MCP Tools   │  │  REST Routes │  │
│  │  (8 tools)   │  │  (CRUD)      │  │
│  └──────┬───────┘  └──────┬───────┘  │
│         │                 │          │
│  ┌──────┴─────────────────┴───────┐  │
│  │  Services Layer                │  │
│  │  - RotationService (failover)  │  │
│  │  - ProviderAdapters (Ollama,   │  │
│  │    OpenRouter, NVIDIA NIM)     │  │
│  └──────────────┬─────────────────┘  │
│                 │                    │
│  ┌──────────────┴─────────────────┐  │
│  │  SQLAlchemy Async (database)   │  │
│  └──────────────┬─────────────────┘  │
└─────────────────┼────────────────────┘
                  │
                  ▼
         ┌────────────────┐
         │  PostgreSQL 16 │
         │  - providers   │
         │  - accounts    │
         │  - usage_logs  │
         └────────────────┘
                  ▲
                  │  HTTP (REST)
         ┌────────┴────────┐
         │  React SPA      │
         │  (Dashboard,    │
         │   CRUD Mgmt)    │
         └─────────────────┘
```

### Technology Stack

| Layer | Technology |
|---|---|
| MCP Framework | FastMCP (built on official `mcp` SDK) |
| Web Framework | FastAPI (async, Pydantic validation) |
| ORM | SQLAlchemy 2.0 (async) |
| Database | PostgreSQL 16 |
| Frontend | React + TypeScript + Vite |
| Containerization | Docker Compose |
| Migrations | Alembic |

---

## Database Schema (3 tables)

### `providers`
| Column | Type | Notes |
|---|---|---|
| id | UUID | PK |
| name | VARCHAR(50) | Unique. One of: `ollama`, `openrouter`, `nvidia-nim` |
| display_name | VARCHAR(100) | Human-readable label |
| base_url | VARCHAR(255) | API base URL (configurable per provider) |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

### `accounts`
| Column | Type | Notes |
|---|---|---|
| id | UUID | PK |
| provider_id | UUID | FK → providers.id |
| email | VARCHAR(255) | Account email/identifier |
| api_token | VARCHAR(512) | Encrypted API key/token |
| is_active | BOOLEAN | Whether account is in rotation |
| is_depleted | BOOLEAN | Flagged when credits exhausted |
| credits_remaining | DECIMAL | Last known credit balance |
| last_error | TEXT | Most recent error message |
| requests_count | INTEGER | Total requests made |
| rate_limit_reset | TIMESTAMP | When rate limit resets |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

### `usage_logs`
| Column | Type | Notes |
|---|---|---|
| id | UUID | PK |
| account_id | UUID | FK → accounts.id |
| provider_id | UUID | FK → providers.id |
| model | VARCHAR(255) | Model used |
| request_type | VARCHAR(50) | e.g., `chat` |
| tokens_in | INTEGER | |
| tokens_out | INTEGER | |
| success | BOOLEAN | |
| error_message | TEXT | |
| created_at | TIMESTAMP | |

---

## MCP Tools (8 tools)

| Tool | Input | Output | Description |
|---|---|---|---|
| `chat_completion` | provider, model, messages, options? | response content + account used | Core proxy with auto-failover |
| `list_providers` | — | List of providers + account counts + status | Discovery |
| `list_accounts` | provider_id? | List of accounts with status | Discovery |
| `get_active_account` | provider | Current active account details | Status check |
| `switch_account` | provider | New active account | Manual rotation |
| `add_account` | provider, email, api_token | Created account | Management |
| `remove_account` | account_id | Confirmation | Management |
| `get_status` | — | Full system health, depletion alerts | Monitoring |

---

## Failover Logic (core flow)

```
chat_completion(provider="openrouter", model="gpt-4o", messages=[...])
  │
  ├─► Get active (non-depleted) account for provider
  │     │
  │     ├─► Make API call via provider adapter
  │     │     │
  │     │     ├─► 200 OK ──► Return response + account metadata
  │     │     │
  │     │     └─► Error (429/402/403 + credit keywords)
  │     │           │
  │     │           ├─► Mark account as depleted
  │     │           ├─► Log failure in usage_logs
  │     │           ├─► Promote next available account
  │     │           ├─► Retry request ONCE
  │     │           │     │
  │     │           │     ├─► Success ──► Return response
  │     │           │     └─► Fail ──► Continue to next account
  │     │           │
  │     │           └─► No more accounts ──► Return error:
  │     │                "All N accounts for {provider} are depleted.
  │     │                 Available providers: [list]. Consider switching."
  │     │
  │     └─► No active accounts at all ──► Return "No active accounts for {provider}"
  │
  └─► Provider not found ──► Return "Unknown provider {name}"
```

### Error Detection Patterns

Each provider adapter detects exhaustion via:
- **HTTP status codes**: 429 (rate limit), 402 (payment required), 403 (forbidden with credit message)
- **Error body keywords**: "credit", "quota", "exhausted", "rate limit", "insufficient", "limit reached"
- **Connection errors**: Timeout, connection refused (mark account as potentially unavailable)

---

## Provider Adapters

Each adapter normalizes the provider's API to a common interface:

```
class BaseProviderAdapter(ABC):
    async def chat_completion(
        self, account: Account, model: str, messages: list, **kwargs
    ) -> ChatResult: ...

    async def check_credits(self, account: Account) -> float | None: ...
```

| Provider | API Format | Auth Header | Credit Detection |
|---|---|---|---|
| Ollama | `/api/chat` (custom JSON) | None (local) | N/A (connection errors only) |
| OpenRouter | OpenAI-compatible | `Authorization: Bearer <token>` | 429 + error body |
| NVIDIA NIM | OpenAI-compatible | `Authorization: Bearer <token>` | 402/429 + error body |

---

## File/Directory Structure

```
/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app entry point
│   │   ├── config.py            # Pydantic Settings
│   │   ├── database.py          # AsyncSession engine
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── provider.py
│   │   │   ├── account.py
│   │   │   └── usage_log.py
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── provider.py
│   │   │   └── account.py
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── providers.py
│   │   │   ├── accounts.py
│   │   │   └── usage.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── rotation.py       # RotationService
│   │   │   └── adapters/
│   │   │       ├── __init__.py
│   │   │       ├── base.py
│   │   │       ├── ollama.py
│   │   │       ├── openrouter.py
│   │   │       └── nvidia.py
│   │   └── mcp_server.py         # FastMCP tool definitions
│   ├── mcp_stdio.py              # stdio entry point (for local AI assistants)
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   ├── api/
│   │   │   └── client.ts
│   │   ├── types/
│   │   │   └── index.ts
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx
│   │   │   ├── Providers.tsx
│   │   │   └── Accounts.tsx
│   │   └── components/
│   │       ├── Layout.tsx
│   │       ├── ProviderCard.tsx
│   │       ├── AccountRow.tsx
│   │       └── StatusBadge.tsx
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── nginx.conf
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
└── doc/
    ├── PLAN.md              ← this file
    ├── 01-scaffold.md
    ├── 02-database.md
    ├── 03-backend-api.md
    ├── 04-provider-rotation.md
    ├── 05-mcp-server.md
    ├── 06-frontend.md
    └── 07-integration.md
```

---

## Implementation Steps

| # | Step | Deliverable |
|---|---|---|
| 1 | **Project scaffold & Docker Compose** | Directory structure, `docker-compose.yml`, `Dockerfile`s, `requirements.txt`, `package.json`, `.env.example` |
| 2 | **Database layer** | SQLAlchemy models, Alembic migrations, `database.py` (async engine + sessions) |
| 3 | **REST API (FastAPI)** | CRUD routers for providers/accounts, status endpoint, Pydantic schemas, config |
| 4 | **Provider adapters & rotation service** | Base adapter interface, 3 provider implementations, rotation logic with auto-failover |
| 5 | **MCP server (FastMCP)** | 8 MCP tools, both stdio and Streamable HTTP entry points, database integration |
| 6 | **React frontend** | Dashboard, CRUD pages, API client, responsive layout |
| 7 | **Integration & final wiring** | Health checks, validation scripts, usage docs, end-to-end test scenarios |

---

## Docker Compose Services

```yaml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: account_rotation
      POSTGRES_USER: rotation_user
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U rotation_user -d account_rotation"]
      interval: 5s
      timeout: 5s
      retries: 5

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    depends_on:
      postgres: { condition: service_healthy }
    environment:
      DATABASE_URL: postgresql+asyncpg://rotation_user:${DB_PASSWORD}@postgres/account_rotation
      ENCRYPTION_KEY: ${ENCRYPTION_KEY}
    command: >
      sh -c "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"

  frontend:
    build: ./frontend
    ports:
      - "5173:80"
    depends_on:
      - backend
```

### Connecting AI Assistants

**Local (stdio)** — in `opencode.json`:
```json
{
  "mcp": {
    "account-rotation": {
      "type": "local",
      "command": ["docker", "compose", "exec", "-T", "backend", "python", "-m", "app.mcp_stdio"],
      "enabled": true
    }
  }
}
```

**Remote (HTTP)** — in `opencode.json`:
```json
{
  "mcp": {
    "account-rotation": {
      "type": "remote",
      "url": "http://localhost:8000/mcp",
      "enabled": true
    }
  }
}
```

Same pattern for Claude Code, Cursor, VS Code, etc.
