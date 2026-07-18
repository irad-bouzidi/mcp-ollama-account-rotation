from pydantic import SecretStr

from app.account import Account, AccountsFile


def test_account_model():
    acc = Account(id="test-1", email="test@example.com", api_key="sk-secret")
    assert acc.id == "test-1"
    assert acc.enabled is True
    assert isinstance(acc.api_key, SecretStr)
    assert acc.api_key.get_secret_value() == "sk-secret"


def test_account_disabled():
    acc = Account(id="test-1", email="test@example.com", api_key="sk-secret", enabled=False)
    assert acc.enabled is False


def test_accounts_file():
    accs = AccountsFile(
        accounts=[
            Account(id="a1", email="a1@example.com", api_key="k1"),
            Account(id="a2", email="a2@example.com", api_key="k2"),
        ]
    )
    assert len(accs.accounts) == 2


def test_account_serialization_roundtrip():
    acc = Account(id="test-1", email="test@example.com", api_key="sk-secret", tags=["prod"])
    data = acc.model_dump()
    assert data["id"] == "test-1"
    assert data["api_key"].get_secret_value() == "sk-secret"
    restored = Account.model_validate(
        {"id": "test-1", "email": "test@example.com", "api_key": "sk-secret", "tags": ["prod"]}
    )
    assert restored.id == "test-1"
    assert restored.api_key.get_secret_value() == "sk-secret"
    assert restored.tags == ["prod"]
