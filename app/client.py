from typing import Any

from httpx import AsyncClient, HTTPError, HTTPStatusError, RequestError, Timeout, TimeoutException

from app.config import TimeoutConfig
from app.exceptions import (
    AuthenticationFailed,
    NetworkFailure,
    OllamaRouterError,
    QuotaExceeded,
    RateLimited,
    ServerError,
    UnknownError,
)
from app.models import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    EmbeddingRequest,
    EmbeddingResponse,
    GenerateRequest,
    GenerateResponse,
    ModelInfo,
)


def _classify_error(status_code: int, body: dict[str, Any] | None) -> OllamaRouterError:
    if status_code == 401:
        return AuthenticationFailed(body.get("error", "Unauthorized") if body else "Unauthorized")
    if status_code == 402:
        return QuotaExceeded(body.get("error", "Quota exceeded") if body else "Quota exceeded")
    if status_code == 429:
        return RateLimited(body.get("error", "Rate limited") if body else "Rate limited")
    if 500 <= status_code < 600:
        return ServerError(body.get("error", f"Server error {status_code}") if body else f"Server error {status_code}")
    return UnknownError(body.get("error", f"Unknown error {status_code}") if body else f"Unknown error {status_code}")


class OllamaClient:
    def __init__(self, base_url: str, timeouts: TimeoutConfig) -> None:
        timeout = Timeout(timeouts.request_seconds, connect=timeouts.connect_seconds)
        self._client = AsyncClient(base_url=base_url.rstrip("/"), timeout=timeout)
        self._base_url = base_url.rstrip("/")

    async def chat(self, request: ChatRequest, api_key: str) -> ChatResponse:
        data = await self._post("/api/chat", request.model_dump(), api_key)
        msg = ChatMessage(
            role=data.get("message", {}).get("role", "assistant"), content=data.get("message", {}).get("content", "")
        )
        return ChatResponse(model=data.get("model", request.model), message=msg)

    async def generate(self, request: GenerateRequest, api_key: str) -> GenerateResponse:
        data = await self._post("/api/generate", request.model_dump(), api_key)
        return GenerateResponse(model=data.get("model", request.model), response=data.get("response", ""))

    async def list_models(self, api_key: str) -> list[ModelInfo]:
        data = await self._get("/api/tags", api_key)
        models = []
        for m in data.get("models", []):
            models.append(
                ModelInfo(name=m.get("name", ""), modified_at=m.get("modified_at", ""), size=m.get("size", 0))
            )
        return models

    async def generate_embeddings(self, request: EmbeddingRequest, api_key: str) -> EmbeddingResponse:
        data = await self._post("/api/embed", request.model_dump(), api_key)
        return EmbeddingResponse(model=data.get("model", request.model), embeddings=data.get("embeddings", []))

    async def check_health(self, api_key: str) -> bool:
        try:
            await self._get("/api/tags", api_key)
            return True
        except OllamaRouterError:
            return False

    async def _post(self, path: str, json_data: dict[str, Any], api_key: str) -> dict[str, Any]:
        try:
            resp = await self._client.post(path, json=json_data, headers={"Authorization": f"Bearer {api_key}"})
            resp.raise_for_status()
            result: dict[str, Any] = resp.json()
            return result
        except HTTPStatusError as e:
            body = _try_parse_json(e.response.text)
            raise _classify_error(e.response.status_code, body)
        except (RequestError, TimeoutException) as e:
            raise NetworkFailure(str(e))
        except HTTPError as e:
            raise NetworkFailure(str(e))

    async def _get(self, path: str, api_key: str) -> dict[str, Any]:
        try:
            resp = await self._client.get(path, headers={"Authorization": f"Bearer {api_key}"})
            resp.raise_for_status()
            result: dict[str, Any] = resp.json()
            return result
        except HTTPStatusError as e:
            body = _try_parse_json(e.response.text)
            raise _classify_error(e.response.status_code, body)
        except (RequestError, TimeoutException) as e:
            raise NetworkFailure(str(e))
        except HTTPError as e:
            raise NetworkFailure(str(e))

    async def close(self) -> None:
        await self._client.aclose()


def _try_parse_json(text: str) -> dict[str, Any] | None:
    import json

    try:
        result: dict[str, Any] = json.loads(text)
        return result
    except (json.JSONDecodeError, ValueError):
        return None
