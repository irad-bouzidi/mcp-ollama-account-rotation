import httpx
import pytest
import respx

from app.client import OllamaClient
from app.config import TimeoutConfig
from app.exceptions import (
    AuthenticationFailed,
    NetworkFailure,
    QuotaExceeded,
    RateLimited,
    ServerError,
)
from app.models import ChatMessage, ChatRequest, GenerateRequest


@pytest.fixture
def client():
    return OllamaClient("https://api.ollama.com", TimeoutConfig())


@pytest.mark.asyncio
async def test_chat_success(client):
    with respx.mock(base_url="https://api.ollama.com") as mock:
        mock.post("/api/chat").respond(json={"model": "llama3", "message": {"role": "assistant", "content": "Hello!"}})
        req = ChatRequest(model="llama3", messages=[ChatMessage(role="user", content="Hi")])
        resp = await client.chat(req, "test-key")
        assert resp.message.content == "Hello!"
        assert resp.model == "llama3"


@pytest.mark.asyncio
async def test_generate_success(client):
    with respx.mock(base_url="https://api.ollama.com") as mock:
        mock.post("/api/generate").respond(json={"model": "llama3", "response": "Generated text"})
        req = GenerateRequest(model="llama3", prompt="Write something")
        resp = await client.generate(req, "test-key")
        assert resp.response == "Generated text"


@pytest.mark.asyncio
async def test_list_models(client):
    with respx.mock(base_url="https://api.ollama.com") as mock:
        mock.get("/api/tags").respond(json={"models": [{"name": "llama3", "size": 100}]})
        models = await client.list_models("test-key")
        assert len(models) == 1
        assert models[0].name == "llama3"


@pytest.mark.asyncio
async def test_401_raises_auth_failed(client):
    with respx.mock(base_url="https://api.ollama.com") as mock:
        mock.post("/api/chat").respond(401, json={"error": "Unauthorized"})
        req = ChatRequest(model="llama3", messages=[ChatMessage(role="user", content="Hi")])
        with pytest.raises(AuthenticationFailed):
            await client.chat(req, "bad-key")


@pytest.mark.asyncio
async def test_402_raises_quota_exceeded(client):
    with respx.mock(base_url="https://api.ollama.com") as mock:
        mock.post("/api/chat").respond(402, json={"error": "Quota exceeded"})
        req = ChatRequest(model="llama3", messages=[ChatMessage(role="user", content="Hi")])
        with pytest.raises(QuotaExceeded):
            await client.chat(req, "test-key")


@pytest.mark.asyncio
async def test_429_raises_rate_limited(client):
    with respx.mock(base_url="https://api.ollama.com") as mock:
        mock.post("/api/chat").respond(429, json={"error": "Too many requests"})
        req = ChatRequest(model="llama3", messages=[ChatMessage(role="user", content="Hi")])
        with pytest.raises(RateLimited):
            await client.chat(req, "test-key")


@pytest.mark.asyncio
async def test_500_raises_server_error(client):
    with respx.mock(base_url="https://api.ollama.com") as mock:
        mock.post("/api/chat").respond(500, json={"error": "Internal error"})
        req = ChatRequest(model="llama3", messages=[ChatMessage(role="user", content="Hi")])
        with pytest.raises(ServerError):
            await client.chat(req, "test-key")


@pytest.mark.asyncio
async def test_network_error(client):
    with respx.mock(base_url="https://api.ollama.com") as mock:
        mock.post("/api/chat").side_effect = httpx.RequestError("Connection refused")
        req = ChatRequest(model="llama3", messages=[ChatMessage(role="user", content="Hi")])
        with pytest.raises(NetworkFailure):
            await client.chat(req, "test-key")
