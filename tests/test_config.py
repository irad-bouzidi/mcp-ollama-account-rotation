import tempfile
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from app.config import AppConfig, RetryConfig, load_config


def test_default_config():
    config = AppConfig()
    assert str(config.ollama_base_url) == "https://api.ollama.com/"
    assert config.retry.max_attempts == 3
    assert config.rotation.strategy == "round_robin"
    assert config.health.interval_seconds == 60
    assert config.logging.level == "INFO"


def test_load_valid_yaml():
    data = {"retry": {"max_attempts": 5}, "ollama_base_url": "https://custom.ollama.com"}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(data, f)
        path = Path(f.name)
    try:
        config = load_config(path)
        assert config.retry.max_attempts == 5
        assert "custom.ollama.com" in str(config.ollama_base_url)
    finally:
        path.unlink(missing_ok=True)


def test_load_empty_yaml():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("")
        path = Path(f.name)
    try:
        config = load_config(path)
        assert isinstance(config, AppConfig)
    finally:
        path.unlink(missing_ok=True)


def test_retry_config_validation():
    with pytest.raises(ValidationError):
        RetryConfig(max_attempts=0)


def test_load_invalid_yaml():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("invalid: [yaml: broken")
        path = Path(f.name)
    try:
        with pytest.raises(Exception):
            load_config(path)
    finally:
        path.unlink(missing_ok=True)
