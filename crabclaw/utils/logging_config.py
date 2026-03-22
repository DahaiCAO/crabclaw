"""Logging configuration for Crabclaw with enhanced security."""

import sys
from pathlib import Path
from typing import Literal

from loguru import logger

from crabclaw.utils.audit_logger import SensitiveDataFilter


def setup_logging(
    level: str = "INFO",
    log_file: str | Path | None = None,
    rotation: str = "100 MB",
    retention: str = "30 days",
    format_string: str | None = None,
    enable_console: bool = True,
    enable_sensitive_filter: bool = True,
) -> None:
    """Setup loguru logging configuration with security enhancements.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file. If None, only console logging is enabled.
        rotation: Log rotation size (e.g., "100 MB", "1 GB")
        retention: Log retention period (e.g., "30 days", "7 days")
        format_string: Custom format string
        enable_console: Whether to enable console logging
        enable_sensitive_filter: Whether to filter sensitive data from logs
    """
    logger.remove()

    default_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )

    # Add sensitive data filter
    if enable_sensitive_filter:
        def sensitive_filter(record):
            record["message"] = SensitiveDataFilter.filter(record["message"])
            return record
    else:
        def sensitive_filter(record):
            return record

    if enable_console:
        # Override console level to INFO or higher (keep DEBUG in file if requested)
        console_level = "INFO" if level == "DEBUG" else level
        logger.add(
            sys.stderr,
            format=format_string or default_format,
            level=console_level,
            colorize=True,
            filter=sensitive_filter,
        )

    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        logger.add(
            str(log_path),
            format=format_string or default_format,
            level=level,
            rotation=rotation,
            retention=retention,
            compression="zip",
            serialize=False,
            filter=sensitive_filter,
        )


def add_structured_logging(log_file: str | Path | None = None) -> None:
    """Add JSON structured logging for production environments."""
    import json
    from datetime import datetime

    def serialize_message(record: dict) -> dict:
        """Serialize log record to JSON with sensitive data filtering."""
        message = SensitiveDataFilter.filter(record["message"])
        return {
            "timestamp": datetime.fromisoformat(record["time"].isoformat()),
            "level": record["level"].name,
            "module": record["name"],
            "function": record["function"],
            "line": record["line"],
            "message": message,
            "extra": record.get("extra", {}),
            "exception": str(record.get("exception", ""))
        }

    def json_sink(message):
        record = message.record
        print(json.dumps(serialize_message(record), ensure_ascii=False))

    if log_file:
        logger.add(
            str(log_file),
            format="{message}",
            serialize=True,
            filter=lambda record: True,
        )
    else:
        logger.add(json_sink, format="{message}")


class LogContext:
    """Context manager for adding extra fields to log records."""

    def __init__(self, **kwargs):
        self._context = kwargs
        self._token = None

    def __enter__(self):
        self._token = logger.contextualize(**self._context)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._token:
            logger.detach(self._token)


class SecureLogger:
    """Wrapper for secure logging practices."""
    
    @staticmethod
    def info(message: str, *args, **kwargs):
        """Log info message with sensitive data filtering."""
        filtered = SensitiveDataFilter.filter(message)
        logger.info(filtered, *args, **kwargs)
    
    @staticmethod
    def warning(message: str, *args, **kwargs):
        """Log warning message with sensitive data filtering."""
        filtered = SensitiveDataFilter.filter(message)
        logger.warning(filtered, *args, **kwargs)
    
    @staticmethod
    def error(message: str, *args, **kwargs):
        """Log error message with sensitive data filtering."""
        filtered = SensitiveDataFilter.filter(message)
        logger.error(filtered, *args, **kwargs)
    
    @staticmethod
    def debug(message: str, *args, **kwargs):
        """Log debug message with sensitive data filtering."""
        filtered = SensitiveDataFilter.filter(message)
        logger.debug(filtered, *args, **kwargs)
    
    @staticmethod
    def critical(message: str, *args, **kwargs):
        """Log critical message with sensitive data filtering."""
        filtered = SensitiveDataFilter.filter(message)
        logger.critical(filtered, *args, **kwargs)
    
    @staticmethod
    def exception(message: str, *args, **kwargs):
        """Log exception with sensitive data filtering."""
        filtered = SensitiveDataFilter.filter(message)
        logger.exception(filtered, *args, **kwargs)


# Convenience functions for secure logging
def log_info(message: str, **kwargs):
    """Secure info logging."""
    SecureLogger.info(message, **kwargs)


def log_warning(message: str, **kwargs):
    """Secure warning logging."""
    SecureLogger.warning(message, **kwargs)


def log_error(message: str, **kwargs):
    """Secure error logging."""
    SecureLogger.error(message, **kwargs)


def log_debug(message: str, **kwargs):
    """Secure debug logging."""
    SecureLogger.debug(message, **kwargs)


def log_critical(message: str, **kwargs):
    """Secure critical logging."""
    SecureLogger.critical(message, **kwargs)
