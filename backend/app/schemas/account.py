from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class AccountBase(BaseModel):
    provider_id: UUID
    email: str | None = None
    api_token: str


class AccountCreate(AccountBase):
    pass


class AccountUpdate(BaseModel):
    email: str | None = None
    api_token: str | None = None
    is_active: bool | None = None


class AccountRead(BaseModel):
    id: UUID
    provider_id: UUID
    email: str | None
    is_active: bool
    is_depleted: bool
    credits_remaining: Decimal | None
    last_error: str | None
    requests_count: int
    rate_limit_reset: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
