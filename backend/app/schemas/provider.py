from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ProviderBase(BaseModel):
    name: str
    display_name: str | None = None
    base_url: str | None = None


class ProviderCreate(ProviderBase):
    pass


class ProviderUpdate(BaseModel):
    display_name: str | None = None
    base_url: str | None = None


class ProviderRead(ProviderBase):
    id: UUID
    created_at: datetime
    account_count: int = 0
    active_accounts: int = 0
    depleted_accounts: int = 0

    model_config = {"from_attributes": True}
