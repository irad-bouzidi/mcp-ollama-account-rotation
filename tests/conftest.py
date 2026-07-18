import json
import tempfile
from pathlib import Path

import pytest
import respx

from app.account import Account
from app.account_manager import AccountManager
from app.client import OllamaClient
from app.config import AppConfig, TimeoutConfig
from app.router import Router
from app.storage import StateManager


@pytest.fixture
def sample_accounts():
    return [
        Account(id="acc-1", email="user1@example.com", api_key="key-1"),
        Account(id="acc-2", email="user2@example.com", api_key="key-2"),
        Account(id="acc-3", email="user3@example.com", api_key="key-3"),
    ]


@pytest.fixture
def temp_accounts_file(sample_accounts):
    raw = {
        "accounts": [
            {
                "id": a.id,
                "email": a.email,
                "api_key": a.api_key.get_secret_value(),
                "enabled": a.enabled,
                "tags": a.tags,
            }
            for a in sample_accounts
        ]
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(raw, f)
        path = Path(f.name)
    yield path
    path.unlink(missing_ok=True)


@pytest.fixture
def temp_state_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({}, f)
        path = Path(f.name)
    yield path
    path.unlink(missing_ok=True)


@pytest.fixture
def test_config(temp_accounts_file, temp_state_file):
    return AppConfig(
        accounts_file=temp_accounts_file,
        state_file=temp_state_file,
    )


@pytest.fixture
def account_manager(temp_accounts_file):
    am = AccountManager(temp_accounts_file)
    am.load()
    return am


@pytest.fixture
def state_manager(temp_state_file):
    sm = StateManager(temp_state_file)
    sm.load()
    return sm


@pytest.fixture
def ollama_client():
    client = OllamaClient("https://api.ollama.com", TimeoutConfig())
    yield client
    import anyio

    anyio.run(client.close)


@pytest.fixture
def mock_ollama_server():
    with respx.mock(base_url="https://api.ollama.com") as mock:
        mock.get("/api/tags", headers={"Authorization": "Bearer key-1"}).respond(
            json={"models": [{"name": "llama3", "size": 100}]}
        )
        mock.get("/api/tags", headers={"Authorization": "Bearer key-2"}).respond(
            json={"models": [{"name": "llama3", "size": 100}]}
        )
        mock.get("/api/tags", headers={"Authorization": "Bearer key-3"}).respond(
            json={"models": [{"name": "llama3", "size": 100}]}
        )
        mock.post("/api/chat").respond(json={"model": "llama3", "message": {"role": "assistant", "content": "Hello!"}})
        mock.post("/api/generate").respond(json={"model": "llama3", "response": "Generated text"})
        yield mock


@pytest.fixture
def router(ollama_client, account_manager, state_manager, test_config):
    return Router(ollama_client, account_manager, state_manager, test_config.retry)
