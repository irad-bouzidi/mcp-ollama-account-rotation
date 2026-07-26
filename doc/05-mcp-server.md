# Step 5: MCP Server (FastMCP Tools)

## Goal

Define the 8 MCP tools using FastMCP, create two entry points (stdio for local AI assistants, Streamable HTTP integrated into FastAPI), and wire everything together.

---

## Architecture

The MCP server shares the same service layer (`RotationService`, `ProviderAdapter`) and database session as the FastAPI REST app. It defines tools via `@mcp.tool()` decorators.

```
                        FastMCP Instance
                        ┌─────────────────────────┐
                        │  @mcp.tool()             │
                        │  chat_completion(...)     │
                        │  list_providers()         │
                        │  list_accounts(...)       │
                        │  get_active_account(...)  │
                        │  switch_account(...)      │
                        │  add_account(...)         │
                        │  remove_account(...)      │
                        │  get_status()             │
                        └──────────┬──────────────┘
                                   │
                      ┌────────────┴────────────┐
                      │  RotationService         │
                      │  (shared with REST API)  │
                      └─────────────────────────┘
```

---

## FastMCP Server Definition

**`backend/app/mcp_server.py`**

```python
from fastmcp import FastMCP

mcp = FastMCP("account-rotation")

@mcp.tool()
async def chat_completion(
    provider: str,
    model: str,
    messages: list,
    options: dict | None = None,
) -> str:
    """
    Send a chat completion request through the configured provider.
    Automatically rotates to the next account if the current one hits rate limits
    or credit exhaustion.

    Args:
        provider: Provider name ('openrouter', 'nvidia-nim', 'ollama')
        model: Model identifier (e.g., 'openai/gpt-4o', 'meta/llama-3.1-8b')
        messages: List of message objects with 'role' and 'content' keys
        options: Optional parameters (temperature, max_tokens, etc.)

    Returns:
        The model's response text

    Raises:
        AllAccountsExhausted if all accounts for the provider are depleted
    """
    ...

@mcp.tool()
async def list_providers() -> list[dict]:
    """
    List all configured providers with account counts and availability status.

    Returns:
        List of providers with metadata:
        - id, name, display_name
        - account_count, active_accounts, depleted_accounts
        - has_available: whether at least one account is usable
    """
    ...

@mcp.tool()
async def list_accounts(provider_id: str | None = None) -> list[dict]:
    """
    List all accounts, optionally filtered by provider.

    Args:
        provider_id: UUID of the provider to filter by (optional)

    Returns:
        List of accounts with status information
        (API tokens are never returned)
    """
    ...

@mcp.tool()
async def get_active_account(provider: str) -> dict:
    """
    Get the currently active (first available) account for a provider.

    Args:
        provider: Provider name

    Returns:
        Account details (without API token)
    """
    ...

@mcp.tool()
async def switch_account(provider: str) -> dict:
    """
    Manually switch to the next available account for a provider.

    Useful for testing rotation or preemptively moving to a fresh account.

    Args:
        provider: Provider name

    Returns:
        The new active account details
    """
    ...

@mcp.tool()
async def add_account(
    provider: str,
    email: str,
    api_token: str,
) -> dict:
    """
    Add a new account to a provider.

    Args:
        provider: Provider name to add the account to
        email: Account email or identifier
        api_token: API key/token for the account

    Returns:
        Created account details (without API token)
    """
    ...

@mcp.tool()
async def remove_account(account_id: str) -> dict:
    """
    Remove an account by ID.

    Args:
        account_id: UUID of the account to remove

    Returns:
        Confirmation message
    """
    ...

@mcp.tool()
async def get_status() -> dict:
    """
    Get the overall system status.

    Returns:
        - providers: list of provider statuses
        - any_available: whether any provider has usable accounts
        - depleted_providers: providers where all accounts are depleted
        - suggestion: if no accounts available, suggests which providers
          to check
    """
    ...
```

### Tool Implementation Pattern

Each tool follows this pattern:
1. Get or create an async database session
2. Create a `RotationService` instance with the session
3. Call the appropriate service method
4. Return serializable dicts (FastMCP auto-converts)

```python
from app.database import async_session
from app.services.rotation import RotationService

async def _get_service():
    session = await anext(get_db())  # or use contextlib
    return RotationService(session), session

@mcp.tool()
async def chat_completion(provider: str, model: str, messages: list, **kwargs) -> str:
    svc, session = await _get_service()
    try:
        result = await svc.chat_completion(provider, model, messages, **kwargs)
        return result.content
    finally:
        await session.close()
```

---

## Entry Points

### Stdio Entry Point (for local AI assistants)

**`backend/app/mcp_stdio.py`**

```python
"""Entry point for stdio MCP transport.
Used by local AI assistants (opencode, claude code, etc.) via docker compose exec.
"""
from app.mcp_server import mcp

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

Usage in `opencode.json`:
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

### Streamable HTTP Entry Point (mounted in FastAPI)

**Add to `backend/app/main.py`:**

```python
from app.mcp_server import mcp

# Mount FastMCP's Streamable HTTP app
app.mount("/mcp", mcp.streamable_http_app())
```

The FastAPI app's existing `app/main.py` mounts the MCP server at the `/mcp` path. The FastAPI lifespan already initializes the DB engine, which the MCP server reuses.

---

## Integration with FastAPI

The MCP server needs access to the same database engine that FastAPI initializes. Since FastMCP doesn't have a built-in lifespan dependency injection, we use a module-level approach:

```python
# app/mcp_server.py
from app.database import engine, async_session

# The engine is initialized in app.main.py's lifespan.
# We check if it's set, and if not, initialize it here.
# This allows the MCP stdio entry point to work independently.
```

Alternative: use FastMCP's lifespan support:
```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def mcp_lifespan(server: FastMCP):
    from app.database import init_db
    await init_db()
    yield
    await dispose_db()

mcp = FastMCP("account-rotation", lifespan=mcp_lifespan)
```

---

## Verification

### Stdio transport:
```bash
# Direct test
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | docker compose exec -T backend python -m app.mcp_stdio

# Or use MCP Inspector
docker compose exec backend npx @modelcontextprotocol/inspector python -m app.mcp_stdio
```

### HTTP transport:
```bash
# SSE endpoint
curl -N http://localhost:8000/mcp

# Health check
curl http://localhost:8000/          # should still return {"status": "ok"}
```

### Tool test via API:
```bash
# List tools
curl -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

---

## Files to create

- `backend/app/mcp_server.py`
- `backend/app/mcp_stdio.py`
