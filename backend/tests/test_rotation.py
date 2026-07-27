from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.models.account import Account
from app.services.adapters.base import ChatResult, ProviderError
from app.services.rotation import (
    AllAccountsExhausted,
    NoAvailableAccounts,
    ProviderNotFound,
    RotationService,
)


class TestRotationService:
    """Integration tests using an in-memory SQLite database."""

    async def test_chat_completion_success(self, session, provider, accounts):
        svc = RotationService(session)
        active = [a for a in accounts if a.is_active and not a.is_depleted]

        with patch("app.services.rotation.get_adapter") as mock_get_adapter:
            mock_adapter = mock_get_adapter.return_value
            mock_adapter.chat_completion = AsyncMock(return_value=ChatResult(
                content="Hello!",
                model="test-model",
                tokens_in=10,
                tokens_out=20,
                account_id=active[0].id,
            ))

            result = await svc.chat_completion(
                provider_name=provider.name,
                model="test-model",
                messages=[{"role": "user", "content": "Hi"}],
            )

            assert result.content == "Hello!"
            assert result.model == "test-model"

    async def test_chat_completion_rotates_on_credit_exhausted(
        self, session, provider, accounts
    ):
        svc = RotationService(session)
        active = sorted(
            [a for a in accounts if a.is_active and not a.is_depleted],
            key=lambda a: a.requests_count,
        )
        assert len(active) >= 2

        call_count = 0

        async def mock_chat_completion(account, model, messages, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ProviderError("Out of credits", is_credit_exhausted=True)
            return ChatResult(content="From backup", model=model, account_id=account.id)

        with patch("app.services.rotation.get_adapter") as mock_get_adapter:
            mock_adapter = mock_get_adapter.return_value
            mock_adapter.chat_completion = mock_chat_completion

            result = await svc.chat_completion(
                provider_name=provider.name,
                model="test-model",
                messages=[{"role": "user", "content": "Hi"}],
            )

            assert result.content == "From backup"
            assert call_count == 2

    async def test_chat_completion_rotates_on_rate_limit(
        self, session, provider, accounts
    ):
        svc = RotationService(session)
        call_count = 0

        async def mock_chat_completion(account, model, messages, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ProviderError("Rate limited", is_rate_limit=True)
            return ChatResult(content="From backup", model=model, account_id=account.id)

        with patch("app.services.rotation.get_adapter") as mock_get_adapter:
            mock_adapter = mock_get_adapter.return_value
            mock_adapter.chat_completion = mock_chat_completion

            result = await svc.chat_completion(
                provider_name=provider.name,
                model="test-model",
                messages=[{"role": "user", "content": "Hi"}],
            )

            assert result.content == "From backup"
            assert call_count == 2

    async def test_chat_completion_re_raises_non_rotation_error(
        self, session, provider, accounts
    ):
        svc = RotationService(session)

        with patch("app.services.rotation.get_adapter") as mock_get_adapter:
            mock_adapter = mock_get_adapter.return_value
            mock_adapter.chat_completion = AsyncMock(
                side_effect=ProviderError("Bad request")
            )

            with pytest.raises(ProviderError, match="Bad request"):
                await svc.chat_completion(
                    provider_name=provider.name,
                    model="test-model",
                    messages=[{"role": "user", "content": "Hi"}],
                )

    async def test_chat_completion_no_available_accounts(self, session, provider):
        """No accounts exist at all for this provider."""
        svc = RotationService(session)

        with patch("app.services.rotation.get_adapter") as mock_get_adapter:
            mock_adapter = mock_get_adapter.return_value
            mock_adapter.chat_completion = AsyncMock(
                side_effect=ProviderError("Bad request")
            )

            with pytest.raises(NoAvailableAccounts, match=provider.name):
                await svc.chat_completion(
                    provider_name=provider.name,
                    model="test-model",
                    messages=[{"role": "user", "content": "Hi"}],
                )

    async def test_chat_completion_all_accounts_exhausted(
        self, session, provider, accounts
    ):
        svc = RotationService(session)
        active = [a for a in accounts if a.is_active and not a.is_depleted]

        call_count = 0

        async def mock_chat_completion(account, model, messages, **kwargs):
            nonlocal call_count
            call_count += 1
            raise ProviderError("Out of credits", is_credit_exhausted=True)

        with patch("app.services.rotation.get_adapter") as mock_get_adapter:
            mock_adapter = mock_get_adapter.return_value
            mock_adapter.chat_completion = mock_chat_completion

            with pytest.raises(AllAccountsExhausted) as exc:
                await svc.chat_completion(
                    provider_name=provider.name,
                    model="test-model",
                    messages=[{"role": "user", "content": "Hi"}],
                )

            assert str(len(active)) in str(exc.value)
            assert provider.name in str(exc.value)
            assert call_count == len(active)

    async def test_provider_not_found(self, session):
        svc = RotationService(session)
        with pytest.raises(ProviderNotFound, match="nonexistent"):
            await svc.chat_completion(
                provider_name="nonexistent",
                model="test-model",
                messages=[],
            )

    async def test_get_active_account(self, session, provider, accounts):
        svc = RotationService(session)
        account = await svc.get_active_account(provider.name)
        assert account is not None
        assert account.is_active is True
        assert account.is_depleted is False

    async def test_get_active_account_no_accounts(self, session, provider):
        svc = RotationService(session)
        account = await svc.get_active_account(provider.name)
        assert account is None

    async def test_switch_account(self, session, provider, accounts):
        svc = RotationService(session)
        switched = await svc.switch_account(provider.name)
        assert switched.is_active is True
        assert switched.is_depleted is False

    async def test_switch_account_no_available(self, session, provider):
        svc = RotationService(session)
        with pytest.raises(NoAvailableAccounts, match=provider.name):
            await svc.switch_account(provider.name)

    async def test_reset_account(self, session, provider, accounts):
        svc = RotationService(session)
        depleted = [a for a in accounts if a.is_depleted][0]
        restored = await svc.reset_account(depleted.id)
        assert restored.is_depleted is False
        assert restored.last_error is None

    async def test_reset_account_not_found(self, session):
        svc = RotationService(session)
        with pytest.raises(ValueError, match="not found"):
            await svc.reset_account(uuid4())


# ---------------------------------------------------------------------------
# Error types
# ---------------------------------------------------------------------------

class TestErrorTypes:
    def test_all_accounts_exhausted(self):
        err = AllAccountsExhausted("all gone")
        assert isinstance(err, Exception)
        assert str(err) == "all gone"

    def test_no_available_accounts(self):
        err = NoAvailableAccounts("no accounts")
        assert isinstance(err, Exception)

    def test_provider_not_found(self):
        err = ProviderNotFound("nope")
        assert isinstance(err, Exception)


# ---------------------------------------------------------------------------
# Usage logging and depletion markers
# ---------------------------------------------------------------------------

class TestDepletionMarkers:
    async def test_mark_depleted(self, session, provider, accounts):
        svc = RotationService(session)
        target = [a for a in accounts if a.is_active and not a.is_depleted][0]

        with patch("app.services.rotation.get_adapter") as mock_get_adapter:
            mock_adapter = mock_get_adapter.return_value
            mock_adapter.chat_completion = AsyncMock(
                side_effect=ProviderError("Out of credits", is_credit_exhausted=True)
            )

            with pytest.raises(AllAccountsExhausted):
                await svc.chat_completion(
                    provider_name=provider.name,
                    model="test-model",
                    messages=[{"role": "user", "content": "Hi"}],
                )

        await session.refresh(target)
        assert target.is_depleted is True
        assert "Out of credits" in (target.last_error or "")

    async def test_non_rotation_error_does_not_mark_depleted(
        self, session, provider, accounts
    ):
        svc = RotationService(session)
        active = [a for a in accounts if a.is_active and not a.is_depleted][0]

        with patch("app.services.rotation.get_adapter") as mock_get_adapter:
            mock_adapter = mock_get_adapter.return_value
            mock_adapter.chat_completion = AsyncMock(
                side_effect=ProviderError("Bad request")
            )

            with pytest.raises(ProviderError):
                await svc.chat_completion(
                    provider_name=provider.name,
                    model="test-model",
                    messages=[{"role": "user", "content": "Hi"}],
                )

        await session.refresh(active)
        assert active.is_depleted is False
