import httpx
import pytest
import respx

from app.exceptions import AllAccountsUnhealthy
from app.models import ChatMessage, ChatRequest


@pytest.mark.asyncio
async def test_chat_routing(router):
    with respx.mock(base_url="https://api.ollama.com") as mock:
        mock.post("/api/chat").respond(json={"model": "llama3", "message": {"role": "assistant", "content": "Hello!"}})
        req = ChatRequest(model="llama3", messages=[ChatMessage(role="user", content="Hi")])
        resp = await router.chat(req)
        assert resp.message.content == "Hello!"


@pytest.mark.asyncio
async def test_list_models_routing(router):
    with respx.mock(base_url="https://api.ollama.com") as mock:
        mock.get("/api/tags").respond(json={"models": [{"name": "llama3", "size": 100}]})
        models = await router.list_models()
        assert len(models) == 1
        assert models[0].name == "llama3"


@pytest.mark.asyncio
async def test_rotation_on_failure(router, account_manager):
    account_manager.select("acc-1")
    call_count = 0

    async def side_effect(request):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(402, json={"error": "Quota exceeded"})
        return httpx.Response(200, json={"model": "llama3", "message": {"role": "assistant", "content": "Hello!"}})

    with respx.mock(base_url="https://api.ollama.com") as mock:
        mock.post("/api/chat").mock(side_effect=side_effect)

        req = ChatRequest(model="llama3", messages=[ChatMessage(role="user", content="Hi")])
        resp = await router.chat(req)
        assert resp.message.content == "Hello!"
        active = account_manager.get_active()
        assert active is not None
        assert active.id != "acc-1"


@pytest.mark.asyncio
async def test_all_unhealthy(router, account_manager):
    for a in account_manager.get_all():
        account_manager.mark_unhealthy(a.id)
    account_manager.select("acc-1")

    with respx.mock(base_url="https://api.ollama.com") as mock:
        mock.post("/api/chat").respond(429, json={"error": "Rate limited"})

        req = ChatRequest(model="llama3", messages=[ChatMessage(role="user", content="Hi")])
        with pytest.raises(AllAccountsUnhealthy):
            await router.chat(req)


@pytest.mark.asyncio
async def test_retry_on_rate_limit(router, account_manager):
    account_manager.select("acc-1")

    with respx.mock(base_url="https://api.ollama.com") as mock:
        mock.post("/api/chat").respond(429, json={"error": "Rate limited"})

        req = ChatRequest(model="llama3", messages=[ChatMessage(role="user", content="Hi")])
        with pytest.raises(AllAccountsUnhealthy):
            await router.chat(req)
