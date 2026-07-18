from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from app.account_manager import AccountManager
from app.config import AppConfig
from app.models import ChatMessage, ChatRequest
from app.router import Router


def create_proxy_app(router: Router, account_manager: AccountManager, config: AppConfig) -> Starlette:
    async def chat_completion(request: Request) -> JSONResponse:
        body = await request.json()
        messages = [ChatMessage(role=m["role"], content=m["content"]) for m in body.get("messages", [])]
        req = ChatRequest(
            model=body.get("model", "llama3"),
            messages=messages,
            options=body.get("options", {}),
        )
        resp = await router.chat(req)
        return JSONResponse(
            {
                "id": "chat-1",
                "object": "chat.completion",
                "model": resp.model,
                "choices": [{"message": {"role": resp.message.role, "content": resp.message.content}}],
            }
        )

    async def list_models(request: Request) -> JSONResponse:
        models = await router.list_models()
        return JSONResponse(
            {
                "object": "list",
                "data": [{"id": m.name, "object": "model"} for m in models],
            }
        )

    return Starlette(
        routes=[
            Route("/v1/chat/completions", chat_completion, methods=["POST"]),
            Route("/v1/models", list_models, methods=["GET"]),
        ]
    )
