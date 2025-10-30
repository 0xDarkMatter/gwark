"""Logging configuration and setup."""

import logging
import logging.config
import sys
from pathlib import Path
from typing import Optional

import yaml

from gmail_mcp.config import get_settings
from gmail_mcp.config.constants import LOG_DATE_FORMAT, LOG_FORMAT


def setup_logging(
    log_level: Optional[str] = None,
    log_file: Optional[Path] = None,
    config_file: Optional[Path] = None,
) -> None:
    """Configure logging for the application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file
        config_file: Path to logging configuration YAML file
    """
    settings = get_settings()

    # Try to load from YAML config first
    if config_file and config_file.exists():
        try:
            with open(config_file) as f:
                config = yaml.safe_load(f)
            logging.config.dictConfig(config)
            logging.info(f"Loaded logging configuration from {config_file}")
            return
        except Exception as e:
            print(f"Failed to load logging config from {config_file}: {e}", file=sys.stderr)

    # Fall back to basic configuration
    log_level = log_level or settings.log_level
    log_file = log_file or Path("logs/gmail_mcp.log")

    # Ensure log directory exists
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format=LOG_FORMAT,
        datefmt=LOG_DATE_FORMAT,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )

    # Set specific loggers to WARNING to reduce noise
    logging.getLogger("googleapiclient.discovery").setLevel(logging.WARNING)
    logging.getLogger("google.auth").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    logging.info(f"Logging configured: level={log_level}, file={log_file}")


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)


class StructuredLogger:
    """Structured logging wrapper for better context."""

    def __init__(self, name: str):
        """Initialize structured logger.

        Args:
            name: Logger name
        """
        self.logger = logging.getLogger(name)

    def _format_message(self, message: str, **context) -> str:
        """Format message with context.

        Args:
            message: Log message
            **context: Additional context key-value pairs

        Returns:
            Formatted message
        """
        if context:
            context_str = " | ".join(f"{k}={v}" for k, v in context.items())
            return f"{message} | {context_str}"
        return message

    def debug(self, message: str, **context) -> None:
        """Log debug message with context."""
        self.logger.debug(self._format_message(message, **context))

    def info(self, message: str, **context) -> None:
        """Log info message with context."""
        self.logger.info(self._format_message(message, **context))

    def warning(self, message: str, **context) -> None:
        """Log warning message with context."""
        self.logger.warning(self._format_message(message, **context))

    def error(self, message: str, **context) -> None:
        """Log error message with context."""
        self.logger.error(self._format_message(message, **context))

    def critical(self, message: str, **context) -> None:
        """Log critical message with context."""
        self.logger.critical(self._format_message(message, **context))

    def exception(self, message: str, **context) -> None:
        """Log exception with context."""
        self.logger.exception(self._format_message(message, **context))
