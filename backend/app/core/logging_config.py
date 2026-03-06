"""
Logging configuration for the application.
Configures format, level, and provides a get_logger helper.
"""
import logging
import sys
from typing import Any

# Default format: timestamp, level, name, message
DEFAULT_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def configure_logging(
    level: str = "INFO",
    format_string: str = DEFAULT_FORMAT,
    date_fmt: str = DATE_FORMAT,
) -> None:
    """
    Configure root logger and console handler.
    Call once at application startup (e.g. in main.py lifespan).
    """
    root = logging.getLogger()
    root.setLevel(level.upper())

    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level.upper())
        formatter = logging.Formatter(format_string, datefmt=date_fmt)
        handler.setFormatter(formatter)
        root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Return a logger for the given module/component."""
    return logging.getLogger(name)


def log_request(logger: logging.Logger, method: str, path: str, status_code: int, duration_ms: float) -> None:
    """Log a completed request (for use in middleware or route)."""
    logger.info(
        "request_completed",
        extra={
            "method": method,
            "path": path,
            "status_code": status_code,
            "duration_ms": round(duration_ms, 2),
        },
    )


def log_exception(logger: logging.Logger, message: str, exc: BaseException, **extra: Any) -> None:
    """Log an exception with optional extra context."""
    logger.exception(
        message,
        exc_info=exc,
        extra=extra,
    )
