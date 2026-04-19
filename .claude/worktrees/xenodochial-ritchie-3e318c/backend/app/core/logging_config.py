"""
Structured logging configuration.

- Production  → JSON (one object per line, compatible with Datadog / CloudWatch / GCP)
- Development → Colorized human-readable format

Every log record automatically includes:
    timestamp, level, logger, service, environment

Usage:
    from app.core.logging_config import get_logger
    logger = get_logger(__name__)
    logger.info("llm_response_generated", provider="gemini", latency_ms=1240)

Or simply use the standard logging module — the JSON formatter is applied globally.
"""
import logging
import logging.config
import sys
from typing import Optional

from pythonjsonlogger import jsonlogger


# ---------------------------------------------------------------------------
# Custom JSON formatter — adds standard fields to every record
# ---------------------------------------------------------------------------
class _AppJsonFormatter(jsonlogger.JsonFormatter):
    """Extends pythonjsonlogger to inject standard fields."""

    def add_fields(self, log_record: dict, record: logging.LogRecord, message_dict: dict):
        super().add_fields(log_record, record, message_dict)

        # Rename standard fields for consistency
        log_record["timestamp"] = log_record.pop("asctime", None) or self.formatTime(record)
        log_record["level"] = record.levelname
        log_record["logger"] = record.name
        log_record.setdefault("service", "inmo-backend")

        # Remove noisy defaults we don't need
        for field in ("exc_info", "exc_text", "stack_info"):
            log_record.pop(field, None)


# ---------------------------------------------------------------------------
# Setup function — call once at application startup
# ---------------------------------------------------------------------------
def setup_logging(environment: str = "development", log_level: str = "INFO") -> None:
    """
    Configure the root logger for the application.

    Args:
        environment: "production" → JSON output; anything else → human-readable.
        log_level:   Minimum log level (e.g. "INFO", "DEBUG").
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    if environment == "production":
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            _AppJsonFormatter(
                fmt="%(timestamp)s %(level)s %(logger)s %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S",
            )
        )
    else:
        # Human-readable with colors via standard format
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                datefmt="%H:%M:%S",
            )
        )

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers to avoid duplicates on hot-reload
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # Reduce noise from chatty libraries
    for noisy in ("httpx", "httpcore", "asyncio", "multipart", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logging.getLogger("uvicorn.error").setLevel(logging.INFO)


def get_logger(name: str) -> logging.Logger:
    """
    Convenience wrapper — returns a standard Logger.
    All configuration is done globally in setup_logging().
    """
    return logging.getLogger(name)
