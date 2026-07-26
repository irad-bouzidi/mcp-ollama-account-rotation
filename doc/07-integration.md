# Step 7: Integration & Final Wiring

## Goal

Tie everything together end to end: health checks, environment validation, documentation for AI assistant config, and verification of the complete workflow.

---

## Tasks

### 7.1 Environment Validation

**`backend/app/validate.py`** — startup validation script:
- Check `DATABASE_URL` is set
- Check `ENCRYPTION_KEY` is set
- Verify database connection with a simple query
- Validate encryption key length (must be 32 bytes for Fernet)
- Print configuration summary (without secrets)

Run this in the Docker entry point before starting the app.

### 7.2 Health Check Endpoint

**`GET /health`** on FastAPI:
```json
{
  "status": "ok",
  "version": "1.0.0",
  "database": "connected",
  "providers_configured": 3,
  "total_accounts": 12,
  "available_accounts": 8,
  "depleted_accounts": 4
}
```

Docker Compose health check for backend service:
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s
  timeout: 10s
  retries: 3
```

### 7.3 API Token Encryption

- Use `cryptography.fernet.Fernet` for symmetric encryption of `api_token` in the accounts table
- Encryption key loaded from `ENCRYPTION_KEY` env var
- Decrypt on read in services layer; store encrypted at rest
- Never expose plaintext token in API responses or logs

**`backend/app/services/encryption.py`**
```python
from cryptography.fernet import Fernet

class TokenEncryptor:
    def __init__(self, key: str):
        self.fernet = Fernet(key.encode() if isinstance(key, str) else key)

    def encrypt(self, token: str) -> str:
        return self.fernet.encrypt(token.encode()).decode()

    def decrypt(self, encrypted: str) -> str:
        return self.fernet.decrypt(encrypted.encode()).decode()
```

### 7.4 Docker Entry Point Script

**`backend/entrypoint.sh`**
```bash
#!/bin/sh
set -e

echo "Running environment validation..."
python -m app.validate

echo "Running database migrations..."
alembic upgrade head

echo "Starting server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Update `backend/Dockerfile` to use this entrypoint.

### 7.5 Docker Compose Polish

Final `docker-compose.yml` with:
- All environment variables from `.env`
- Health checks on postgres and backend
- Restart policy: `unless-stopped`
- `depends_on` with condition checks
- Named volumes for postgres data

### 7.6 MCP Configuration Templates

**`doc/opencode-config-example.json`**
```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "account-rotation": {
      "type": "local",
      "command": ["docker", "compose", "exec", "-T", "backend", "python", "-m", "app.mcp_stdio"],
      "enabled": true
    }
  },
  "instructions": "You have access to the Account Rotation MCP server. Use it to manage AI provider accounts and send chat completions through available accounts. When an account is depleted, the system automatically rotates. If all accounts for a provider are exhausted, suggest the user to add new accounts or switch providers."
}
```

Also include examples for:
- Claude Code (`~/.claude/settings.json`)
- VS Code (`.vscode/mcp.json`)
- Cursor (`.cursor/mcp.json`)

### 7.7 End-to-End Verification Scenarios

Document and test these scenarios:

**Scenario 1: Basic workflow**
1. `docker compose up -d`
2. Open frontend at `http://localhost:5173`
3. Verify dashboard loads with no providers
4. Add provider "openrouter" via frontend
5. Add 2 accounts for openrouter
6. Verify dashboard shows 2 accounts, both available
7. Call `chat_completion` via MCP → succeeds

**Scenario 2: Auto-failover**
1. Add 2 accounts for openrouter
2. Manually set account A as depleted (via API: `POST /api/accounts/{id}/toggle`)
3. Set account B's API token to an invalid one
4. Call `chat_completion` → fails with error, marks B as errored
5. Reset account A (`POST /api/accounts/{id}/reset`)
6. Call `chat_completion` → succeeds using account A

**Scenario 3: All accounts exhausted**
1. Add 1 account for openrouter
2. Mark it depleted manually
3. Call `chat_completion` → returns "All accounts for openrouter are depleted..."
4. Dashboard shows red warning banner
5. Add provider "nvidia-nim" with an account
6. Dashboard shows green status again
7. Call `chat_completion(provider="nvidia-nim")` → succeeds

**Scenario 4: MCP stdio transport**
1. `docker compose exec -T backend python -m app.mcp_stdio`
2. Send JSON-RPC via stdin → verify tool list returned
3. Test in opencode via the config template

**Scenario 5: Token encryption**
1. Add account with token `sk-test123`
2. Verify in database: `SELECT api_token FROM accounts;` → encrypted value (not plaintext)
3. Call `chat_completion` → token is decrypted in memory, API call succeeds

### 7.8 README.md

Write a concise `README.md` with:
- Project description
- Quick start (`docker compose up`)
- How to configure AI assistants (opencode, claude code, VS Code)
- Provider setup guide (getting API keys)
- Architecture overview (brief)
- Directory structure

### 7.9 .env.example (final)

```ini
# PostgreSQL
DB_PASSWORD=change_me_in_production

# Encryption (generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
ENCRYPTION_KEY=change_me_too_a_32_byte_key_base64_encoded==

# Optional: Ollama host (if running separately)
OLLAMA_BASE_URL=http://host.docker.internal:11434

# Debug mode
DEBUG=false
```

### 7.10 Verification Checklist

- [ ] `docker compose build` succeeds without errors
- [ ] `docker compose up -d` starts all 3 services
- [ ] `curl http://localhost:8000/health` returns 200 with DB connected
- [ ] `curl http://localhost:5173/` returns React SPA HTML
- [ ] Can create a provider via frontend
- [ ] Can create an account via frontend
- [ ] Can list providers via MCP tool
- [ ] `chat_completion` works with a real API token
- [ ] Token is encrypted at rest in PostgreSQL
- [ ] Auto-failover works: depleted account → next account
- [ ] All-depleted error returned when no accounts available
- [ ] Dashboard correctly shows depletion status
- [ ] README documents all configuration steps

## Files to create

- `backend/app/validate.py`
- `backend/app/services/encryption.py`
- `backend/entrypoint.sh`
- `doc/opencode-config-example.json`
- `README.md` (root)
