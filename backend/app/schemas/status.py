from uuid import UUID

from pydantic import BaseModel

from app.schemas.account import AccountRead


class ProviderStatus(BaseModel):
    id: UUID
    name: str
    display_name: str | None
    total_accounts: int
    active_accounts: int
    depleted_accounts: int
    has_available: bool
    current_active_account: AccountRead | None


class SystemStatus(BaseModel):
    providers: list[ProviderStatus]
    any_available: bool
    depleted_providers: list[str]
