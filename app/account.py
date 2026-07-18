from pydantic import BaseModel, SecretStr


class Account(BaseModel):
    id: str
    email: str
    api_key: SecretStr
    enabled: bool = True
    tags: list[str] = []


class AccountsFile(BaseModel):
    accounts: list[Account]
