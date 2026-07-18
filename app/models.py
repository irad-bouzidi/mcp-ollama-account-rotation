from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    stream: bool = False
    options: dict[str, object] = {}


class ChatResponse(BaseModel):
    model: str
    message: ChatMessage
    done: bool = True


class GenerateRequest(BaseModel):
    model: str
    prompt: str
    stream: bool = False
    options: dict[str, object] = {}


class GenerateResponse(BaseModel):
    model: str
    response: str
    done: bool = True


class ModelInfo(BaseModel):
    name: str
    modified_at: str = ""
    size: int = 0


class EmbeddingRequest(BaseModel):
    model: str
    input: str | list[str]


class EmbeddingResponse(BaseModel):
    model: str
    embeddings: list[list[float]]


class HealthCheckResult(BaseModel):
    healthy: bool
    account_id: str
    latency_ms: float = 0.0
    error: str | None = None
