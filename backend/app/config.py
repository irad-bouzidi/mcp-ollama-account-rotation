from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://rotation_user:password@localhost/account_rotation"
    encryption_key: str = ""
    debug: bool = False

    model_config = {"env_prefix": "", "case_sensitive": False}


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
