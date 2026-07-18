# mcp-ollama-account-rotation — Implementation Plan

## Overview

Build an MCP server that transparently routes Ollama Cloud API requests across multiple user-owned accounts, handling quota exhaustion, rate limits, and failures via automatic account rotation.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        MCP Client                            │
│              (Claude Code / OpenCode / etc.)                 │
└─────────────────────┬────────────────────────────────────────┘
                      │
                      │ MCP Protocol (stdio / SSE)
                      ▼
┌──────────────────────────────────────────────────────────────┐
│                 FastMCP Server  (app/server.py)               │
│                                                              │
│  ┌────────────────────────────────────────────────────┐     │
│  │  Tools Layer     (chat, generate, list_models)     │     │
│  │  Resource Layer  (models://, accounts://)          │     │
│  │  Sampling Capability (model provider)             │     │
│  └──────────────────────┬────────────────────────────┘     │
│                         │                                   │
│  ┌──────────────────────▼────────────────────────────┐     │
│  │              Request Router  (app/router.py)        │     │
│  │  • select account    • forward request             │     │
│  │  • classify error    • trigger rotation            │     │
│  └──────┬─────────────────────────────┬──────────────┘     │
│         │                             │                      │
│  ┌──────▼──────────────┐  ┌──────────▼──────────────┐     │
│  │  Account Manager     │  │  Retry Engine           │     │
│  │  (app/account_       │  │  (app/retry.py)         │     │
│  │   manager.py)        │  │  • tenacity             │     │
│  │  • load/save JSON    │  │  • exp. backoff+jitter  │     │
│  │  • select/rotate     │  └──────────┬──────────────┘     │
│  │  • track health      │             │                      │
│  └──────┬───────────────┘  ┌──────────▼──────────────┐     │
│         │                  │  Ollama HTTP Client      │     │
│  ┌──────▼───────────────┐  │  (app/client.py)        │     │
│  │  State Manager        │  │  • httpx.AsyncClient   │     │
│  │  (app/storage.py)     │  │  • error classification│     │
│  │  • runtime state      │  └──────────┬──────────────┘     │
│  │  • thread-safe        │             │                      │
│  │  • auto-save          │  ┌──────────▼──────────────┐     │
│  └───────────────────────┘  │  Ollama Cloud API        │     │
│                              │  https://api.ollama.com  │     │
│  ┌───────────────────────┐  └─────────────────────────┘     │
│  │  Health Checker       │                                   │
│  │  (app/health.py)      │                                   │
│  │  • periodic probes    │                                   │
│  │  • auto-recovery      │                                   │
│  └───────────────────────┘                                   │
│                                                              │
│  ┌───────────────────────┐  ┌───────────────────────┐      │
│  │  Logger & Metrics     │  │  OpenAI Proxy (opt.)  │      │
│  │  (app/logging.py)     │  │  (app/proxy.py)       │      │
│  └───────────────────────┘  └───────────────────────┘      │
└──────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
ollama-router-mcp/
├── app/
│   ├── __init__.py            # Package metadata, version
│   ├── __main__.py            # CLI entry point
│   ├── server.py              # FastMCP server, tool definitions, lifecycle
│   ├── router.py              # Request router, rotation orchestration
│   ├── account_manager.py     # Account loading, selection, health tracking
│   ├── account.py             # Account Pydantic model
│   ├── models.py              # Request/response Pydantic models
│   ├── config.py              # AppConfig Pydantic model, YAML loading
│   ├── client.py              # Ollama Cloud HTTP client (httpx)
│   ├── exceptions.py          # Custom exception hierarchy
│   ├── storage.py             # Runtime state persistence
│   ├── quota.py               # Quota tracking logic
│   ├── health.py              # Background health checker
│   ├── retry.py               # Retry decorator / logic
│   ├── logging.py             # Structured logging setup (structlog)
│   ├── utils.py               # Shared utilities
│   └── proxy.py               # (Optional) OpenAI-compatible HTTP proxy
├── data/
│   ├── accounts.json          # Account credentials (user-managed)
│   ├── state.json             # Runtime state (auto-managed)
│   └── config.yaml            # Server configuration
├── tests/
│   ├── __init__.py
│   ├── conftest.py            # Shared fixtures
│   ├── test_config.py
│   ├── test_account.py
│   ├── test_account_manager.py
│   ├── test_state.py
│   ├── test_client.py
│   ├── test_router.py
│   ├── test_retry.py
│   ├── test_health.py
│   ├── test_server.py
│   ├── test_rotation.py
│   └── test_logging.py
├── requirements.txt           # Pinned dependencies
├── pyproject.toml             # Build config, metadata, dev deps
└── README.md                  # Full documentation
```

---

## Phases

### Phase 1 — Project Scaffolding

- Create directory tree
- `pyproject.toml` with all dependencies and entry point
- `requirements.txt` (pinned)
- `app/__init__.py` — version string, exports
- `app/__main__.py` — CLI arg parser, launches server
- `data/accounts.json` — empty array
- `data/state.json` — empty state object
- `data/config.yaml` — default configuration
- `tests/__init__.py`
- Verify `pip install -e .` works

**Dependencies:**
- `mcp>=1.0.0` — Anthropic MCP SDK
- `httpx>=0.28.0` — Async HTTP client
- `pydantic>=2.0.0` — Data validation
- `pyyaml>=6.0` — YAML parsing
- `tenacity>=9.0.0` — Retry logic
- `structlog>=24.0.0` — Structured logging
- `watchfiles>=1.0.0` — File system watching
- `anyio>=4.0.0` — Async runtime

**Dev dependencies:**
- `pytest>=8.0`
- `pytest-asyncio>=0.24`
- `pytest-cov>=5.0`
- `respx>=0.22` — Mock httpx at wire level
- `mypy>=1.10`
- `ruff>=0.5`
- `pyyaml-include>=2.0`

---

### Phase 2 — Configuration System

**File: `app/config.py`**

- `AppConfig` Pydantic model with nested configs:
  - `ollama_base_url: HttpUrl`
  - `retry: RetryConfig` (max_attempts, backoff_base, backoff_max, jitter)
  - `rotation: RotationConfig` (strategy: "round_robin")
  - `health: HealthConfig` (interval_seconds, timeout_seconds, test_prompt)
  - `timeouts: TimeoutConfig` (request_seconds, connect_seconds)
  - `logging: LoggingConfig` (level, format, output)
  - `accounts_file: Path`
  - `state_file: Path`
- `load_config(path: Path) -> AppConfig` — load YAML, validate with Pydantic
- `get_default_config() -> AppConfig` — fallback defaults
- Config file watching / reload detection

---

### Phase 3 — Account Management

**File: `app/account.py`**

- `Account(BaseModel)` — id, email, api_key (SecretStr), enabled, tags
- `AccountsFile(BaseModel)` — accounts: list[Account]

**File: `app/account_manager.py`**

- `AccountManager` class:
  - `load()` — read JSON → validate → store in dict
  - `get_active()` → current `Account`
  - `get_all()` → list of enabled accounts
  - `select(account_id)` — set active
  - `mark_unhealthy(id)` — add to skip set
  - `mark_healthy(id)` — remove from skip set
  - `is_healthy(id) → bool`
  - `rotate() → Account` — round-robin across healthy accounts
  - `start_watcher()` — `watchfiles.awatch` background task
  - `stop_watcher()`
- Thread safety via `threading.Lock`
- Live reload on file change (re-read JSON, merge state)

---

### Phase 4 — State Persistence

**File: `app/storage.py`**

- `AccountState(BaseModel)` — status, failure_count, last_error, last_used, request_count
- `RuntimeState(BaseModel)` — active_account, last_rotation, accounts: dict[str, AccountState]
- `StateManager` class:
  - `load()` / `save()` — JSON I/O
  - `get_active_account()`, `set_active_account(id)`
  - `record_failure(account_id, error)`, `record_success(account_id)`
  - `record_request(account_id)`
  - `set_status(account_id, status)`
  - `auto_save(interval)` — background debounced flush
- Thread safety via `threading.RLock`
- Atomic writes (write to temp file, rename)

---

### Phase 5 — HTTP Client

**File: `app/exceptions.py`**

- `OllamaRouterError(BaseException)`
  - `QuotaExceeded`
  - `AuthenticationFailed`
  - `RateLimited`
  - `NetworkFailure`
  - `ServerError`
  - `AccountDisabled`
  - `UnknownError`

**File: `app/models.py`**

- Request/response models:
  - `ChatMessage`, `ChatRequest`, `ChatResponse`
  - `GenerateRequest`, `GenerateResponse`
  - `ModelInfo`
  - `EmbeddingRequest`, `EmbeddingResponse`
  - `HealthCheckResult`

**File: `app/client.py`**

- `OllamaClient` class:
  - `__init__(base_url, timeouts)` — creates `httpx.AsyncClient`
  - `async chat(request, api_key) → ChatResponse`
  - `async generate(request, api_key) → GenerateResponse`
  - `async list_models(api_key) → list[ModelInfo]`
  - `async generate_embeddings(request, api_key) → EmbeddingResponse`
  - `async check_health(api_key) → bool`
  - `_classify_error(response) → OllamaRouterError` — maps status + body to exception type
  - `close()` — cleanup

---

### Phase 6 — Request Router

**File: `app/router.py`**

- `Router` class:
  - `__init__(client, account_manager, state_manager, retry_config)`
  - `async chat(request) → ChatResponse`
  - `async generate(request) → GenerateResponse`
  - `async list_models() → list[ModelInfo]`
  - `_execute_with_rotation(method_name, request, **kwargs)` — core logic:
    1. Acquire async lock
    2. Select healthy account (rotate if needed)
    3. Attach API key
    4. Call client method
    5. On non-retryable error: mark unhealthy, rotate, retry up to N times
    6. On retryable error: mark unhealthy, rotate, retry
    7. On success: record success, return response
    8. If all accounts unhealthy: raise `AllAccountsUnhealthy`

---

### Phase 7 — MCP Server Implementation

**File: `app/server.py`**

- Create `FastMCP` instance with metadata
- Server lifecycle via `@mcp.startup()` / `@mcp.shutdown()`
- Tools:
  - `chat(model, messages, options) → str` — chat completion
  - `generate(model, prompt, options) → str` — text generation
  - `list_models() → list[dict]` — available models
  - `get_account_status() → dict` — current account info
  - `get_metrics() → dict` — server metrics
- Resources:
  - `models://list` — model list (static resource)
  - `accounts://current` — active account info
  - `accounts://all` — all accounts and their statuses
- Prompts (optional): `chat` template
- Sampling: declare capability, handle `sampling/createMessage` by proxying to Ollama
- CLI entry point (`__main__.py`):
  - `--config` / `-c` path to config
  - `--transport` stdio (default) or sse
  - `--port` for SSE transport

---

### Phase 8 — Retry and Rotation

**File: `app/retry.py`**

- `build_retry_decorator(config)` — creates tenacity retry with:
  - `stop_after_attempt`
  - `wait_exponential` + `wait_random` for jitter
  - `retry_if_exception` for retryable exceptions
- `is_retryable(exc) → bool` — `RateLimited`, `ServerError`, `NetworkFailure` are retryable; `AuthenticationFailed`, `QuotaExceeded`, `AccountDisabled` trigger immediate rotation
- `is_rotation_trigger(exc) → bool` — any server-side failure triggers rotation

**Rotation Strategy:**
- `RoundRobinRotation` class:
  - Maintains sorted list of account IDs and current index
  - `next(healthy_filter) → Optional[str]` — returns next healthy account, or `None`
  - Wraps around, skips unhealthy
  - If all unhealthy, returns `None` → router raises `AllAccountsUnhealthy`

---

### Phase 9 — Health Monitoring

**File: `app/health.py`**

- `HealthChecker` class:
  - `__init__(client, account_manager, state_manager, config)`
  - `async start()` — spawn background task
  - `async stop()` — cancel task
  - `_run()` — loop: for each unhealthy account, probe; sleep interval
  - `_probe(account) → bool`:
    - Send lightweight request (e.g., list models or generate short text)
    - On success: mark healthy, log recovery, update state
    - On failure: log debug, increment probe count
  - Probe backoff: unhealthy accounts checked less frequently (exponential backoff on probe interval per account)

---

### Phase 10 — Logging and Metrics

**File: `app/logging.py`**

- `configure_logging(config)` — set up structlog with:
  - JSON renderer (console) or file output
  - ISO timestamp processor
  - Level filtering
  - Sensitive data redaction processor (replaces `api_key`, `Authorization` header, `email` with `[REDACTED]`)
- `get_logger(name) → BoundLogger`

**Metrics:**
```python
@dataclass
class ServerMetrics:
    uptime_start: datetime
    total_requests: int
    successful_requests: int
    failed_requests: int
    retries: int
    rotations: int
    per_account: dict[str, AccountMetrics]
```
- Thread-safe via `threading.Lock`
- Updated by router on each request
- Exposed via `get_metrics()` tool

**Log events:**
| Event | When |
|---|---|
| `startup` | Server starts |
| `shutdown` | Server stops |
| `request_received` | Tool called |
| `account_selected` | Account chosen for request |
| `account_rotated` | Rotated to different account |
| `retry_attempt` | Retrying failed request |
| `quota_failure` | Quota exceeded |
| `auth_failure` | Authentication failed |
| `network_failure` | Network/connection error |
| `account_recovered` | Health check succeeded |
| `config_reloaded` | Config file changed |
| `all_accounts_unhealthy` | No healthy accounts available |

---

### Phase 11 — Testing

**Conftest (`tests/conftest.py`):**
- `sample_accounts` fixture — 3 test accounts
- `mock_ollama_server` fixture — respx mock for api.ollama.com
- `temp_accounts_file` fixture — tmpdir JSON
- `temp_state_file` fixture — tmpdir JSON
- `test_config` fixture — config with test values
- `account_manager` fixture — pre-loaded with sample accounts
- `state_manager` fixture — clean state
- `ollama_client` fixture — real client with mocked HTTP
- `router` fixture — wired together

**Test files and coverage:**

| File | What it tests |
|---|---|
| `test_config.py` | Load valid/invalid YAML, defaults, validation errors |
| `test_account.py` | Account model, SecretStr, serialization round-trip |
| `test_account_manager.py` | Load, reload, select, rotate, mark unhealthy/healthy, file watching (mock), concurrent access |
| `test_state.py` | Save/load, thread safety, concurrent mutations, auto-save debounce |
| `test_client.py` | Success response, 401→AuthFailed, 429→RateLimited, 402→QuotaExceeded, 5xx→ServerError, connection error→NetworkFailure, timeouts |
| `test_router.py` | Basic routing, rotation on failure, all-unhealthy, mixed success/failure |
| `test_retry.py` | Decorator behavior, max attempts, backoff calculation, non-retryable pass-through |
| `test_health.py` | Probe success→recovery, probe failure→stays unhealthy, no-op when healthy |
| `test_server.py` | Tool registration, lifecycle callbacks, MCP protocol message handling |
| `test_rotation.py` | Round-robin order, skip unhealthy, wrap-around, all-unhealthy edge case |
| `test_logging.py` | Redaction of secrets, JSON format validity, event emission |

**Async concurrent tests:**
```python
async def test_concurrent_requests(router, mock_ollama_server):
    """10 concurrent requests, verify no races."""

async def test_rotation_under_load(router, mock_ollama_server):
    """Fail account mid-rotation under load, verify orderly recovery."""
```

---

### Phase 12 — Documentation

**File: `README.md`**

Sections:
1. **Overview** — purpose, features, transparency claim
2. **Architecture** — ASCII diagram, component descriptions
3. **Installation**
   - Prerequisites (Python 3.11+)
   - `pip install -e .`
   - `uv sync` alternative
4. **Configuration** — `config.yaml` reference with all options
5. **Account Setup**
   - `data/accounts.json` format
   - Adding/removing accounts
   - Credential management (`.env` support)
6. **Usage with MCP Clients**
   - **Claude Code** — `claude.json` config
   - **OpenCode** — `opencode.json` config
   - **Generic MCP client** — stdio and SSE
7. **Transparent Backend Integration**
   - Configuring coding agent to use the router as its LLM provider
   - OpenAI-compatible proxy endpoint (if `proxy.py` is enabled)
8. **Troubleshooting** — common errors, log inspection, health checks
9. **Logging** — log format, searching logs, redaction
10. **Metrics** — available metrics, interpretation
11. **Development**
    - Setting up dev environment
    - Running tests (`pytest`)
    - Type checking (`mypy`)
    - Linting (`ruff`)
12. **Contributing** — PR guidelines, code style

---

### Phase 13 — Final Refactoring

1. **Type checking** — `mypy --strict` pass, fix all issues
2. **Linting** — `ruff check --fix`, `ruff format`
3. **Docstrings** — verify all public APIs have docstrings (Google style)
4. **Edge cases**:
   - Empty accounts file
   - All accounts disabled
   - All accounts unhealthy
   - Config file deleted at runtime
   - Accounts file deleted at runtime
   - Network unavailable at startup
   - Rapid file changes (debounce)
5. **Thread safety audit** — every shared mutable state access is protected
6. **Secret audit** — grep for `api_key`, `password`, `secret` in log paths; verify redaction
7. **Graceful shutdown** — SIGTERM/SIGINT handlers, flush state, close connections
8. **Performance** — connection reuse, minimal allocations, async hot paths
9. **README final pass**
10. **Changelog / version bump**

---

## Dependency Justification

| Library | Why |
|---|---|
| `mcp` | Official Anthropic MCP SDK — only guaranteed compatible implementation |
| `httpx` | Async HTTP with connection pooling, timeouts, rich error handling |
| `pydantic` | Validation at every boundary (config, accounts, requests, responses) |
| `pyyaml` | YAML config per user preference |
| `tenacity` | Battle-tested retry with all strategies built in |
| `structlog` | Production-grade structured logging with built-in redaction |
| `watchfiles` | Async file watching (faster than polling) |
| `anyio` | Async runtime used by mcp; supports asyncio and trio |
| `respx` (dev) | Mock httpx at the wire level — no real network in tests |
