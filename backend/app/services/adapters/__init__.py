from app.services.adapters.base import BaseProviderAdapter
from app.services.adapters.openrouter import OpenRouterAdapter
from app.services.adapters.nvidia import NVIDIAAdapter
from app.services.adapters.ollama import OllamaAdapter

ADAPTER_REGISTRY: dict[str, type[BaseProviderAdapter]] = {
    "openrouter": OpenRouterAdapter,
    "nvidia-nim": NVIDIAAdapter,
    "ollama": OllamaAdapter,
}


def get_adapter(provider_name: str) -> BaseProviderAdapter:
    cls = ADAPTER_REGISTRY.get(provider_name)
    if not cls:
        raise ValueError(f"Unknown provider: {provider_name}")
    return cls()
