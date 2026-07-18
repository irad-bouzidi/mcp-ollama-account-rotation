import structlog
from structlog.stdlib import BoundLogger

from app.config import LoggingConfig

_SECRET_FIELDS = {"api_key", "authorization", "email", "password", "secret", "token"}


def _redact_processor(logger, method_name, event_dict):  # type: ignore[no-untyped-def]
    for key in list(event_dict.keys()):
        if key.lower() in _SECRET_FIELDS:
            event_dict[key] = "[REDACTED]"
    if isinstance(event_dict.get("event"), dict):
        for key in list(event_dict["event"].keys()):
            if key.lower() in _SECRET_FIELDS:
                event_dict["event"][key] = "[REDACTED]"
    return event_dict


def configure_logging(config: LoggingConfig) -> None:
    processors = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.dev.set_exc_info,
        _redact_processor,
    ]

    if config.format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,  # type: ignore[arg-type]
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> BoundLogger:
    return structlog.get_logger(name)  # type: ignore[no-any-return]
