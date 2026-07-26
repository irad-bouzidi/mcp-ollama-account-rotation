from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.usage_log import UsageLog

router = APIRouter(prefix="/api/usage", tags=["usage"])


class UsageLogRead(BaseModel):
    id: UUID
    account_id: UUID
    provider_id: UUID
    model: str
    request_type: str
    tokens_in: int | None
    tokens_out: int | None
    success: bool
    error_message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginatedUsage(BaseModel):
    items: list[UsageLogRead]
    total: int
    page: int
    page_size: int


@router.get("", response_model=PaginatedUsage)
async def list_usage(
    account_id: UUID | None = Query(None),
    provider_id: UUID | None = Query(None),
    model: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    base = select(UsageLog)
    count_base = select(func.count()).select_from(UsageLog)

    if account_id is not None:
        base = base.where(UsageLog.account_id == account_id)
        count_base = count_base.where(UsageLog.account_id == account_id)
    if provider_id is not None:
        base = base.where(UsageLog.provider_id == provider_id)
        count_base = count_base.where(UsageLog.provider_id == provider_id)
    if model is not None:
        base = base.where(UsageLog.model == model)
        count_base = count_base.where(UsageLog.model == model)

    total_result = await db.execute(count_base)
    total = total_result.scalar() or 0

    result = await db.execute(
        base.order_by(UsageLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = result.scalars().all()

    return PaginatedUsage(
        items=[UsageLogRead.model_validate(u) for u in items],
        total=total,
        page=page,
        page_size=page_size,
    )
