from contextlib import asynccontextmanager
from uuid import UUID

from fastmcp import FastMCP
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import async_session, engine
from app.models.account import Account
from app.models.provider import Provider
from app.services.rotation import AllAccountsExhausted, NoAvailableAccounts, RotationService


@asynccontextmanager
async def mcp_lifespan(server: FastMCP):
    async with engine.connect() as conn:
        await conn.run_sync(lambda _: None)
    yield


mcp = FastMCP("account-rotation", lifespan=mcp_lifespan)


async def _get_service():
    session = async_session()
    return RotationService(session), session


def _account_to_dict(account: Account) -> dict:
    return {
        "id": str(account.id),
        "provider_id": str(account.provider_id),
        "email": account.email,
        "is_active": account.is_active,
        "is_depleted": account.is_depleted,
        "credits_remaining": float(account.credits_remaining) if account.credits_remaining is not None else None,
        "last_error": account.last_error,
        "requests_count": account.requests_count,
        "rate_limit_reset": account.rate_limit_reset.isoformat() if account.rate_limit_reset else None,
    }


@mcp.tool()
async def chat_completion(
    provider: str,
    model: str,
    messages: list,
    options: dict | None = None,
) -> str:
    """
    Send a chat completion request through the configured provider.
    Automatically rotates to the next account if the current one hits rate limits
    or credit exhaustion.

    Args:
        provider: Provider name ('openrouter', 'nvidia-nim', 'ollama')
        model: Model identifier (e.g., 'openai/gpt-4o', 'meta/llama-3.1-8b')
        messages: List of message objects with 'role' and 'content' keys
        options: Optional parameters (temperature, max_tokens, etc.)

    Returns:
        The model's response text
    """
    svc, session = await _get_service()
    try:
        kwargs = options or {}
        result = await svc.chat_completion(provider, model, messages, **kwargs)
        return result.content
    finally:
        await session.close()


@mcp.tool()
async def list_providers() -> list[dict]:
    """
    List all configured providers with account counts and availability status.

    Returns:
        List of providers with metadata:
        - id, name, display_name
        - account_count, active_accounts, depleted_accounts
        - has_available: whether at least one account is usable
    """
    session = async_session()
    try:
        result = await session.execute(
            select(Provider).options(selectinload(Provider.accounts))
        )
        providers = result.scalars().all()

        output = []
        for p in providers:
            accounts = p.accounts
            active_accounts = sum(1 for a in accounts if a.is_active)
            depleted_accounts = sum(1 for a in accounts if a.is_depleted)
            available = [a for a in accounts if a.is_active and not a.is_depleted]

            output.append({
                "id": str(p.id),
                "name": p.name,
                "display_name": p.display_name,
                "account_count": len(accounts),
                "active_accounts": active_accounts,
                "depleted_accounts": depleted_accounts,
                "has_available": len(available) > 0,
            })
        return output
    finally:
        await session.close()


@mcp.tool()
async def list_accounts(provider_id: str | None = None) -> list[dict]:
    """
    List all accounts, optionally filtered by provider.

    Args:
        provider_id: UUID of the provider to filter by (optional)

    Returns:
        List of accounts with status information (API tokens are never returned)
    """
    session = async_session()
    try:
        stmt = select(Account).options(selectinload(Account.provider))
        if provider_id is not None:
            stmt = stmt.where(Account.provider_id == UUID(provider_id))
        result = await session.execute(stmt)
        accounts = result.scalars().all()
        return [_account_to_dict(a) for a in accounts]
    finally:
        await session.close()


@mcp.tool()
async def get_active_account(provider: str) -> dict:
    """
    Get the currently active (first available) account for a provider.

    Args:
        provider: Provider name

    Returns:
        Account details (without API token)
    """
    svc, session = await _get_service()
    try:
        account = await svc.get_active_account(provider)
        if account is None:
            return {"error": f"No active accounts available for provider '{provider}'"}
        return _account_to_dict(account)
    finally:
        await session.close()


@mcp.tool()
async def switch_account(provider: str) -> dict:
    """
    Manually switch to the next available account for a provider.

    Useful for testing rotation or preemptively moving to a fresh account.

    Args:
        provider: Provider name

    Returns:
        The new active account details
    """
    svc, session = await _get_service()
    try:
        account = await svc.switch_account(provider)
        return _account_to_dict(account)
    except NoAvailableAccounts:
        return {"error": f"No available accounts to switch to for provider '{provider}'"}
    finally:
        await session.close()


@mcp.tool()
async def add_account(
    provider: str,
    email: str,
    api_token: str,
) -> dict:
    """
    Add a new account to a provider.

    Args:
        provider: Provider name to add the account to
        email: Account email or identifier
        api_token: API key/token for the account

    Returns:
        Created account details (without API token)
    """
    session = async_session()
    try:
        result = await session.execute(
            select(Provider).where(Provider.name == provider)
        )
        prov = result.scalar_one_or_none()
        if prov is None:
            return {"error": f"Provider '{provider}' not found"}

        account = Account(
            provider_id=prov.id,
            email=email,
            api_token=api_token,
        )
        session.add(account)
        await session.commit()
        await session.refresh(account)
        return _account_to_dict(account)
    finally:
        await session.close()


@mcp.tool()
async def remove_account(account_id: str) -> dict:
    """
    Remove an account by ID.

    Args:
        account_id: UUID of the account to remove

    Returns:
        Confirmation message
    """
    session = async_session()
    try:
        result = await session.execute(
            select(Account).where(Account.id == UUID(account_id))
        )
        account = result.scalar_one_or_none()
        if account is None:
            return {"error": f"Account '{account_id}' not found"}

        await session.delete(account)
        await session.commit()
        return {"success": True, "message": f"Account '{account_id}' removed"}
    finally:
        await session.close()


@mcp.tool()
async def get_status() -> dict:
    """
    Get the overall system status.

    Returns:
        - providers: list of provider statuses
        - any_available: whether any provider has usable accounts
        - depleted_providers: providers where all accounts are depleted
        - suggestion: if no accounts available, suggests which providers to check
    """
    session = async_session()
    try:
        result = await session.execute(
            select(Provider).options(selectinload(Provider.accounts))
        )
        providers = result.scalars().all()

        provider_list = []
        depleted_names = []

        for p in providers:
            accounts = p.accounts
            active_accounts = sum(1 for a in accounts if a.is_active)
            depleted_accounts = sum(1 for a in accounts if a.is_depleted)
            available = [a for a in accounts if a.is_active and not a.is_depleted]
            current = available[0] if available else None

            if len(accounts) > 0 and depleted_accounts == len(accounts):
                depleted_names.append(p.name)

            provider_list.append({
                "id": str(p.id),
                "name": p.name,
                "display_name": p.display_name,
                "total_accounts": len(accounts),
                "active_accounts": active_accounts,
                "depleted_accounts": depleted_accounts,
                "has_available": len(available) > 0,
                "current_active_account": _account_to_dict(current) if current else None,
            })

        any_available = any(p["has_available"] for p in provider_list)
        suggestion = None
        if not any_available:
            suggestion = (
                f"All accounts are depleted. "
                f"Depleted providers: {', '.join(depleted_names) if depleted_names else 'none'}. "
                f"Use add_account to add new credentials or reset_account to reset depleted ones."
            )

        return {
            "providers": provider_list,
            "any_available": any_available,
            "depleted_providers": depleted_names,
            "suggestion": suggestion,
        }
    finally:
        await session.close()
