from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.account import Account
from app.models.provider import Provider
from app.schemas.account import AccountCreate, AccountRead, AccountUpdate

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


async def _get_account_or_404(db: AsyncSession, account_id: UUID) -> Account:
    result = await db.execute(select(Account).where(Account.id == account_id))
    account = result.scalar_one_or_none()
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


def _to_account_read(account: Account) -> AccountRead:
    return AccountRead(
        id=account.id,
        provider_id=account.provider_id,
        email=account.email,
        is_active=account.is_active,
        is_depleted=account.is_depleted,
        credits_remaining=account.credits_remaining,
        last_error=account.last_error,
        requests_count=account.requests_count,
        rate_limit_reset=account.rate_limit_reset,
        created_at=account.created_at,
    )


@router.get("", response_model=list[AccountRead])
async def list_accounts(
    provider_id: UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Account)
    if provider_id is not None:
        stmt = stmt.where(Account.provider_id == provider_id)
    result = await db.execute(stmt)
    return [_to_account_read(a) for a in result.scalars().all()]


@router.get("/{account_id}", response_model=AccountRead)
async def get_account(account_id: UUID, db: AsyncSession = Depends(get_db)):
    account = await _get_account_or_404(db, account_id)
    return _to_account_read(account)


@router.post("", response_model=AccountRead, status_code=201)
async def create_account(
    data: AccountCreate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Provider).where(Provider.id == data.provider_id)
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Provider not found")

    account = Account(
        provider_id=data.provider_id,
        email=data.email,
        api_token=data.api_token,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return _to_account_read(account)


@router.put("/{account_id}", response_model=AccountRead)
async def update_account(
    account_id: UUID,
    data: AccountUpdate,
    db: AsyncSession = Depends(get_db),
):
    account = await _get_account_or_404(db, account_id)
    if data.email is not None:
        account.email = data.email
    if data.api_token is not None:
        account.api_token = data.api_token
    if data.is_active is not None:
        account.is_active = data.is_active
    await db.commit()
    await db.refresh(account)
    return _to_account_read(account)


@router.delete("/{account_id}", status_code=204)
async def delete_account(account_id: UUID, db: AsyncSession = Depends(get_db)):
    account = await _get_account_or_404(db, account_id)
    await db.delete(account)
    await db.commit()


@router.post("/{account_id}/toggle", response_model=AccountRead)
async def toggle_account(account_id: UUID, db: AsyncSession = Depends(get_db)):
    account = await _get_account_or_404(db, account_id)
    account.is_active = not account.is_active
    await db.commit()
    await db.refresh(account)
    return _to_account_read(account)


@router.post("/{account_id}/reset", response_model=AccountRead)
async def reset_account(account_id: UUID, db: AsyncSession = Depends(get_db)):
    account = await _get_account_or_404(db, account_id)
    account.is_depleted = False
    await db.commit()
    await db.refresh(account)
    return _to_account_read(account)
