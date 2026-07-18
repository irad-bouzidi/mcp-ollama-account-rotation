# mcp-ollama-account-rotation

MCP server that transparently routes Ollama Cloud API requests across multiple user-owned accounts, handling quota exhaustion, rate limits, and failures via automatic account rotation.

## Architecture

```
┌──────────────────────────────────────────┐
│              MCP Client                   │
│    (Claude Code / OpenCode / etc.)       │
└─────────────────┬────────────────────────┘
                  │ MCP Protocol (stdio/SSE)
                  ▼
┌──────────────────────────────────────────┐
│          FastMCP Server                   │
│   Tools: chat, generate, list_models     │
│   Resources: models://, accounts://      │
├──────────────────────────────────────────┤
│          Request Router                   │
│   select account → forward → classify    │
├──────────────────────────────────────────┤
│   Account Manager    │   Retry Engine    │
│   State Manager      │   Health Checker  │
│   HTTP Client        │   Logger/Metrics  │
└──────────────────────────────────────────┘
                  │
                  ▼
         Ollama Cloud API
    https://api.ollama.com
```

## Installation

```bash
# Prerequisites: Python 3.11+
pip install -e .
# Or with uv:
uv sync
```

## Configuration

Edit `data/config.yaml`:

```yaml
ollama_base_url: "https://api.ollama.com"
retry:
  max_attempts: 3
  backoff_base: 2.0
  backoff_max: 60.0
  jitter: 0.1
rotation:
  strategy: "round_robin"
health:
  interval_seconds: 60
  timeout_seconds: 10
timeouts:
  request_seconds: 60
  connect_seconds: 10
logging:
  level: "INFO"
  format: "json"
  output: "console"
```

## Account Setup

Add accounts to `data/accounts.json`:

```json
{
  "accounts": [
    {
      "id": "personal",
      "email": "user1@example.com",
      "api_key": "ollama-api-key-1",
      "enabled": true,
      "tags": ["prod"]
    },
    {
      "id": "work",
      "email": "user2@example.com",
      "api_key": "ollama-api-key-2",
      "enabled": true,
      "tags": ["prod"]
    }
  ]
}
```

## Usage

### CLI

```bash
# stdio transport (default)
ollama-router

# custom config
ollama-router -c /path/to/config.yaml

# SSE transport
ollama-router --transport sse --port 8000
```

### MCP Client Integration

**OpenCode** (`opencode.json`):
```json
{
  "mcpServers": {
    "ollama-router": {
      "command": "ollama-router",
      "args": ["-c", "data/config.yaml"]
    }
  }
}
```

**Claude Code** (`claude.json`):
```json
{
  "mcpServers": {
    "ollama-router": {
      "command": "ollama-router",
      "args": ["-c", "data/config.yaml"]
    }
  }
}
```

## Tools

| Tool | Description |
|------|-------------|
| `chat` | Send chat completion request |
| `generate` | Send text generation request |
| `list_models` | List available models |
| `get_account_status` | Show current active account |
| `get_metrics` | Show server metrics |

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Type checking
mypy app

# Linting
ruff check app
ruff format app
```

## Log Events

| Event | Description |
|-------|-------------|
| `startup` | Server starts |
| `shutdown` | Server stops |
| `account_selected` | Account chosen for request |
| `account_rotated` | Rotated to different account |
| `retry_attempt` | Retrying failed request |
| `account_recovered` | Health check succeeded |
| `all_accounts_unhealthy` | No healthy accounts |

## License

MIT
