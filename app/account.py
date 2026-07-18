import re

from pydantic import BaseModel, SecretStr, model_validator


def _email_to_id(email: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", email.split("@")[0])


class Account(BaseModel):
    id: str | None = None
    email: str
    api_key: SecretStr
    enabled: bool = True
    tags: list[str] = []

    @model_validator(mode="after")
    def _default_id(self) -> "Account":
        if self.id is None and self.email:
            self.id = _email_to_id(self.email)
        return self


class AccountsFile(BaseModel):
    accounts: list[Account]
