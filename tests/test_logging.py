from app.logging import _redact_processor


def test_redact_api_key():
    event = {"api_key": "sk-secret-123", "event": "test"}
    result = _redact_processor(None, None, event)
    assert result["api_key"] == "[REDACTED]"


def test_redact_authorization():
    event = {"Authorization": "Bearer sk-secret", "event": "test"}
    result = _redact_processor(None, None, event)
    assert result["Authorization"] == "[REDACTED]"


def test_redact_email():
    event = {"email": "user@example.com", "event": "test"}
    result = _redact_processor(None, None, event)
    assert result["email"] == "[REDACTED]"


def test_redact_event_dict():
    event = {"event": {"api_key": "secret-key", "email": "user@example.com"}}
    result = _redact_processor(None, None, event)
    assert result["event"]["api_key"] == "[REDACTED]"
    assert result["event"]["email"] == "[REDACTED]"


def test_allow_regular_fields():
    event = {"account_id": "acc-1", "model": "llama3", "response": "hello"}
    result = _redact_processor(None, None, event)
    assert result["account_id"] == "acc-1"
    assert result["model"] == "llama3"
    assert result["response"] == "hello"
