from sqlalchemy import select

from app.database import async_session
from app.models.provider import Provider


DEFAULT_PROVIDERS = [
    {"name": "ollama", "display_name": "Ollama", "base_url": "http://host.docker.internal:11434"},
    {"name": "openrouter", "display_name": "OpenRouter", "base_url": "https://openrouter.ai/api/v1"},
    {"name": "nvidia-nim", "display_name": "NVIDIA NIM", "base_url": "https://integrate.api.nvidia.com/v1"},
]


async def seed_providers():
    async with async_session() as session:
        result = await session.execute(select(Provider).limit(1))
        if result.scalar_one_or_none() is not None:
            return

        for data in DEFAULT_PROVIDERS:
            provider = Provider(**data)
            session.add(provider)

        await session.commit()
