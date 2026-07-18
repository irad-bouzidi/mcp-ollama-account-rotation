import re

from pydantic import BaseModel, SecretStr, field_validator


def _email_to_id(email: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", email.split("@")[0])


class Account(BaseModel):
    id: str | None = None
    email: str
    api_key: SecretStr
    enabled: bool = True
    tags: list[str] = []

    @field_validator("id", mode="before")
    @classmethod
    def _default_id(cls, v: str | None, info) -> str:
        if v:
            return v
        email = info.data.get("email")
        if email:
            return _email_to_id(str(email))
        return "unknown"


class AccountsFile(BaseModel):
    accounts: list[Account]
