"""Centralized logging for Sparkth.

The single public entry point for logging. All modules — application code and
plugins alike — must obtain loggers via :func:`get_logger`, never
``logging.getLogger`` directly. Logging is configured exactly once per process
via :func:`configure_logging`, which is the only ``logging.basicConfig`` call in
the codebase.

Example:
    ```python
    from app.lib.log import get_logger

    logger = get_logger(__name__)
    logger.info("This is a log message")
    ```
"""

import logging
import sys

# Shared log format for the whole application.
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def configure_logging(level: int = logging.INFO) -> None:
    """Configure root logging once for the whole process.

    This is the only place in the codebase that calls ``logging.basicConfig``.
    It is idempotent: ``basicConfig`` is a no-op if the root logger already has
    handlers, so calling it from multiple entrypoints is safe.

    Args:
        level: Root logging level (defaults to ``INFO``).
    """
    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        datefmt=DATE_FORMAT,
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def get_logger(name: str) -> logging.Logger:
    """Return the Sparkth logger for ``name`` (typically ``__name__``).

    Loggers are namespaced under ``sparkth.`` and propagate to the root logger
    configured by :func:`configure_logging`.

    Args:
        name: Logger name, typically ``__name__`` of the calling module.

    Returns:
        Logger instance.
    """
    return logging.getLogger(f"sparkth.{name}")
