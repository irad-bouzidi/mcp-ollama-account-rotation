from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.provider import Provider
from app.schemas.provider import ProviderCreate, ProviderRead, ProviderUpdate

router = APIRouter(prefix="/api/providers", tags=["providers"])


async def _get_provider_with_accounts(
    db: AsyncSession, provider_id: UUID,
) -> Provider:
    result = await db.execute(
        select(Provider)
        .options(selectinload(Provider.accounts))
        .where(Provider.id == provider_id)
    )
    provider = result.scalar_one_or_none()
    if provider is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    return provider


def _to_provider_read(provider: Provider) -> ProviderRead:
    accounts = provider.accounts
    return ProviderRead(
        id=provider.id,
        name=provider.name,
        display_name=provider.display_name,
        base_url=provider.base_url,
        created_at=provider.created_at,
        account_count=len(accounts),
        active_accounts=sum(1 for a in accounts if a.is_active),
        depleted_accounts=sum(1 for a in accounts if a.is_depleted),
    )


@router.get("", response_model=list[ProviderRead])
async def list_providers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Provider).options(selectinload(Provider.accounts))
    )
    return [_to_provider_read(p) for p in result.scalars().all()]


@router.get("/{provider_id}", response_model=ProviderRead)
async def get_provider(provider_id: UUID, db: AsyncSession = Depends(get_db)):
    provider = await _get_provider_with_accounts(db, provider_id)
    return _to_provider_read(provider)


@router.post("", response_model=ProviderRead, status_code=201)
async def create_provider(
    data: ProviderCreate, db: AsyncSession = Depends(get_db),
):
    provider = Provider(
        name=data.name,
        display_name=data.display_name,
        base_url=data.base_url,
    )
    db.add(provider)
    try:
        await db.commit()
        await db.refresh(provider)
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=409, detail="Provider with this name already exists"
        )
    return ProviderRead(
        id=provider.id,
        name=provider.name,
        display_name=provider.display_name,
        base_url=provider.base_url,
        created_at=provider.created_at,
        account_count=0,
        active_accounts=0,
        depleted_accounts=0,
    )


@router.put("/{provider_id}", response_model=ProviderRead)
async def update_provider(
    provider_id: UUID,
    data: ProviderUpdate,
    db: AsyncSession = Depends(get_db),
):
    provider = await _get_provider_with_accounts(db, provider_id)
    if data.display_name is not None:
        provider.display_name = data.display_name
    if data.base_url is not None:
        provider.base_url = data.base_url
    await db.commit()
    return _to_provider_read(provider)


@router.delete("/{provider_id}", status_code=204)
async def delete_provider(provider_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Provider).where(Provider.id == provider_id)
    )
    provider = result.scalar_one_or_none()
    if provider is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    await db.delete(provider)
    await db.commit()

