# AGENTS.md — mcp-ollama-account-rotation

## What this is

MCP server that proxies Ollama Cloud API requests across multiple
user-owned accounts with automatic rotation on quota/rate-limit/failure.

## Entrypoint & CLI

- Entry: `app/__main__.py:main` → `ollama-router` console script
  (defined in `pyproject.toml: [project.scripts]`)
- Transports: `--transport stdio` (default) or `--transport sse --port 8000`
- Config path: `-c data/config.yaml` (default)
- Docker: `docker compose up` runs SSE on `:8000`

## Key modules

| Module | Role |
|--------|------|
| `server.py` | FastMCP low-level `Server` wiring; tools & resources |
| `router.py` | Orchestrates account selection, call, rotation on failure |
| `client.py` | `httpx.AsyncClient` wrapper; error classification (401→Auth, 402→Quota, 429→RateLimit, 5xx→Server) |
| `account_manager.py` | Loads/serves accounts from JSON; round-robin rotation; thread-safe |
| `storage.py` | Persists runtime state to `data/state.json`; atomic writes |
| `health.py` | Background checker probing unhealthy accounts; **start()/stop() never called** |
| `retry.py` | Sync decorator + `RoundRobinRotation` (unused by router; router has inline retry) |
| `config.py` | Pydantic models for `data/config.yaml` |
| `proxy.py` | Optional OpenAI-compatible HTTP proxy (`/v1/chat/completions`) |
| `exceptions.py` | Error hierarchy: QuotaExceeded, AuthFailed, RateLimited, NetworkFailure, etc. |

## Data files

- `data/config.yaml` — server settings (auto-created if missing)
- `data/accounts.json` — user-managed, gitignored account list
- `data/state.json` — auto-managed runtime state (per-account health, counts)

## Dev commands

```bash
pytest                        # asyncio_mode = auto
pytest tests/test_file.py     # single file
pytest -k "test_name"         # single test
ruff check app                # lint (line-length 120, target py311)
ruff format app               # format
mypy app                      # strict mode
```

## Testing conventions

- `respx` mocks `httpx` at wire level; no real network
- Fixtures in `tests/conftest.py`: `sample_accounts`, `temp_accounts_file`,
  `temp_state_file`, `test_config`, `account_manager`, `state_manager`,
  `ollama_client`, `mock_ollama_server`, `router`
- `mock_ollama_server` fixture provides pre-wired respx routes for
  `/api/tags`, `/api/chat`, `/api/generate`
- `pytest-asyncio` with `asyncio_mode = auto` (no need for `@pytest.mark.asyncio`)

## Notable quirks / missing pieces

- **HealthChecker created but never started** — `start()`/`stop()` not called
  in `create_server()` (background probe loop never runs)
- **`retry.py` unused** — `retry_with_backoff` decorator and `RoundRobinRotation`
  exist but are dead code; router manages retries and rotation inline
- **No `quota.py`** despite being listed in `PLAN.md`
- **No CI** — no `.github/` workflows
- **Sync + async mixing** — `AccountManager` and `StateManager` use
  `threading.Lock`/`RLock` (called from async context via `anyio`); `retry.py`
  uses `time.sleep()` (sync only)
- **Open-code only** — no `opencode.json`, `CLAUDE.md`, or `.cursor/` config present
