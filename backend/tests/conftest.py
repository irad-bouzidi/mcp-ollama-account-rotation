from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.database import Base
from app.models.account import Account
from app.models.provider import Provider
from app.services.adapters.base import ChatResult

ASYNC_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="session")
async def engine():
    engine = create_async_engine(ASYNC_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def session(engine) -> AsyncGenerator[AsyncSession, None]:
    connection = await engine.connect()
    transaction = await connection.begin()
    async_session = async_sessionmaker(bind=connection, expire_on_commit=False)
    async with async_session() as s:
        yield s
        await transaction.rollback()
        await connection.close()


@pytest_asyncio.fixture
async def provider(session: AsyncSession) -> Provider:
    p = Provider(
        id=uuid4(),
        name="test-provider",
        display_name="Test Provider",
        base_url="https://api.test.com/v1",
    )
    session.add(p)
    await session.commit()
    return p


@pytest_asyncio.fixture
async def accounts(session: AsyncSession, provider: Provider) -> list[Account]:
    accs = [
        Account(
            id=uuid4(),
            provider_id=provider.id,
            email="primary@test.com",
            api_token="tok-primary",
            is_active=True,
            is_depleted=False,
            requests_count=0,
        ),
        Account(
            id=uuid4(),
            provider_id=provider.id,
            email="backup@test.com",
            api_token="tok-backup",
            is_active=True,
            is_depleted=False,
            requests_count=5,
        ),
        Account(
            id=uuid4(),
            provider_id=provider.id,
            email="depleted@test.com",
            api_token="tok-depleted",
            is_active=True,
            is_depleted=True,
            requests_count=10,
        ),
        Account(
            id=uuid4(),
            provider_id=provider.id,
            email="inactive@test.com",
            api_token="tok-inactive",
            is_active=False,
            is_depleted=False,
            requests_count=2,
        ),
    ]
    for a in accs:
        session.add(a)
    await session.commit()
    return accs


class FakeResponse:
    def __init__(self, status_code: int, json_data: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.text = text

    def json(self):
        return self._json_data


@pytest.fixture
def mock_chat_result() -> ChatResult:
    return ChatResult(
        content="Hello, world!",
        model="test-model",
        tokens_in=10,
        tokens_out=20,
        account_id=uuid4(),
    )
