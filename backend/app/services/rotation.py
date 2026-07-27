from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.account import Account
from app.models.provider import Provider
from app.models.usage_log import UsageLog
from app.services.adapters.base import ChatResult, ProviderError
from app.services.adapters import ADAPTER_REGISTRY, get_adapter


class AllAccountsExhausted(Exception):
    """All accounts for a provider are depleted."""


class NoAvailableAccounts(Exception):
    """No active, non-depleted accounts for the provider."""


class ProviderNotFound(Exception):
    """Unknown provider name."""


class RotationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def chat_completion(
        self, provider_name: str, model: str, messages: list, **kwargs
    ) -> ChatResult:
        provider = await self._get_provider(provider_name)
        adapter = get_adapter(provider.name)

        accounts = await self._get_available_accounts(provider.id)
        if not accounts:
            raise NoAvailableAccounts(provider_name)

        errors: list[str] = []
        for account in accounts:
            try:
                result = await adapter.chat_completion(
                    account, model, messages, **kwargs
                )
                await self._log_usage(
                    account.id, provider.id, model, result, success=True
                )
                await self._increment_requests(account.id)
                return result

            except ProviderError as e:
                await self._log_usage(
                    account.id,
                    provider.id,
                    model,
                    None,
                    success=False,
                    error=str(e),
                )
                errors.append(str(e))

                if e.is_credit_exhausted or e.is_rate_limit:
                    await self._mark_depleted(account.id, str(e))
                    continue
                else:
                    raise

        available_providers = await self._get_available_providers()
        raise AllAccountsExhausted(
            f"All {len(accounts)} accounts for {provider_name} are depleted. "
            f"Available providers: {available_providers}. Consider switching."
        )

    async def get_active_account(self, provider_name: str) -> Account | None:
        provider = await self._get_provider(provider_name)
        accounts = await self._get_available_accounts(provider.id)
        return accounts[0] if accounts else None

    async def switch_account(self, provider_name: str) -> Account:
        provider = await self._get_provider(provider_name)
        result = await self.db.execute(
            select(Account)
            .where(
                Account.provider_id == provider.id,
                Account.is_active == True,
                Account.is_depleted == False,
            )
            .options(selectinload(Account.provider))
            .order_by(Account.requests_count.asc())
            .offset(1)
            .limit(1)
        )
        account = result.scalar_one_or_none()
        if not account:
            raise NoAvailableAccounts(provider_name)
        return account

    async def reset_account(self, account_id: UUID) -> Account:
        await self.db.execute(
            update(Account)
            .where(Account.id == account_id)
            .values(is_depleted=False, last_error=None, rate_limit_reset=None)
        )
        await self.db.commit()
        result = await self.db.execute(
            select(Account)
            .where(Account.id == account_id)
            .options(selectinload(Account.provider))
        )
        account = result.scalar_one_or_none()
        if not account:
            raise ValueError(f"Account {account_id} not found")
        return account

    async def _get_provider(self, provider_name: str) -> Provider:
        result = await self.db.execute(
            select(Provider).where(Provider.name == provider_name)
        )
        provider = result.scalar_one_or_none()
        if not provider:
            raise ProviderNotFound(provider_name)
        return provider

    async def _get_available_accounts(self, provider_id: UUID) -> list[Account]:
        result = await self.db.execute(
            select(Account)
            .where(
                Account.provider_id == provider_id,
                Account.is_active == True,
                Account.is_depleted == False,
            )
            .options(selectinload(Account.provider))
            .order_by(Account.requests_count.asc())
        )
        return list(result.scalars().all())

    async def _log_usage(
        self,
        account_id: UUID,
        provider_id: UUID,
        model: str,
        result: ChatResult | None,
        success: bool,
        error: str | None = None,
    ):
        log = UsageLog(
            account_id=account_id,
            provider_id=provider_id,
            model=model,
            request_type="chat",
            tokens_in=result.tokens_in if result else None,
            tokens_out=result.tokens_out if result else None,
            success=success,
            error_message=error,
        )
        self.db.add(log)
        await self.db.commit()

    async def _increment_requests(self, account_id: UUID):
        await self.db.execute(
            update(Account)
            .where(Account.id == account_id)
            .values(requests_count=Account.requests_count + 1)
        )
        await self.db.commit()

    async def _mark_depleted(self, account_id: UUID, error: str):
        await self.db.execute(
            update(Account)
            .where(Account.id == account_id)
            .values(is_depleted=True, last_error=error)
        )
        await self.db.commit()

    async def _get_available_providers(self) -> list[str]:
        registry_names = list(ADAPTER_REGISTRY.keys())
        result = await self.db.execute(
            select(Provider.name).where(Provider.name.in_(registry_names))
        )
        return [row[0] for row in result.all()]
