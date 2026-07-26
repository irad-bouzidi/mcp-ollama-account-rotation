from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.alembic import run_migrations
from app.config import get_settings
from app.database import get_db
from app.models.provider import Provider
from app.routers import accounts, providers, usage
from app.schemas.account import AccountRead
from app.schemas.status import ProviderStatus, SystemStatus
from app.seed import seed_providers


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    await run_migrations(settings.database_url)
    await seed_providers()
    yield


app = FastAPI(title="Account Rotation API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:80"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(providers.router)
app.include_router(accounts.router)
app.include_router(usage.router)


@app.get("/")
async def root():
    return {"status": "ok"}


@app.get("/api/status", response_model=SystemStatus)
async def system_status(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Provider).options(selectinload(Provider.accounts))
    )
    providers = result.scalars().all()

    status_list: list[ProviderStatus] = []
    depleted_names: list[str] = []

    for p in providers:
        accounts = p.accounts
        active_accounts = sum(1 for a in accounts if a.is_active)
        depleted_accounts = sum(1 for a in accounts if a.is_depleted)
        available = [a for a in accounts if a.is_active and not a.is_depleted]
        has_available = len(available) > 0
        current = available[0] if available else None

        if len(accounts) > 0 and depleted_accounts == len(accounts):
            depleted_names.append(p.name)

        status_list.append(
            ProviderStatus(
                id=p.id,
                name=p.name,
                display_name=p.display_name,
                total_accounts=len(accounts),
                active_accounts=active_accounts,
                depleted_accounts=depleted_accounts,
                has_available=has_available,
                current_active_account=(
                    AccountRead.model_validate(current) if current else None
                ),
            )
        )

    return SystemStatus(
        providers=status_list,
        any_available=any(s.has_available for s in status_list),
        depleted_providers=depleted_names,
    )
