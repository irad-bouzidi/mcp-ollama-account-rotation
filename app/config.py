from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, HttpUrl, field_validator


class RetryConfig(BaseModel):
    max_attempts: int = 3
    backoff_base: float = 2.0
    backoff_max: float = 60.0
    jitter: float = 0.1

    @field_validator("max_attempts")
    @classmethod
    def max_attempts_must_be_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("max_attempts must be >= 1")
        return v


class RotationConfig(BaseModel):
    strategy: Literal["round_robin"] = "round_robin"


class HealthConfig(BaseModel):
    interval_seconds: int = 60
    timeout_seconds: int = 10
    test_prompt: str = "hello"

    @field_validator("interval_seconds", "timeout_seconds")
    @classmethod
    def must_be_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("must be >= 1")
        return v


class TimeoutConfig(BaseModel):
    request_seconds: int = 60
    connect_seconds: int = 10

    @field_validator("request_seconds", "connect_seconds")
    @classmethod
    def must_be_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("must be >= 1")
        return v


class LoggingConfig(BaseModel):
    level: str = "INFO"
    format: Literal["json", "console"] = "json"
    output: Literal["console", "file"] = "console"


class AppConfig(BaseModel):
    ollama_base_url: HttpUrl = HttpUrl("https://api.ollama.com")
    retry: RetryConfig = RetryConfig()
    rotation: RotationConfig = RotationConfig()
    health: HealthConfig = HealthConfig()
    timeouts: TimeoutConfig = TimeoutConfig()
    logging: LoggingConfig = LoggingConfig()
    accounts_file: Path = Path("data/accounts.json")
    state_file: Path = Path("data/state.json")


def load_config(path: Path) -> AppConfig:
    with open(path) as f:
        raw = yaml.safe_load(f)
    if raw is None:
        raw = {}
    return AppConfig.model_validate(raw)


def get_default_config() -> AppConfig:
    return AppConfig()
