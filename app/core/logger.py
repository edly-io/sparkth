"""
Centralized Logging Configuration

Provides a consistent logging setup across the entire application.
All modules should import and use the logger from this module.
"""

import logging
import sys
from pathlib import Path
from typing import Optional

# Configure default logging format
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logger(
    name: str = "sparkth",
    level: int = logging.INFO,
    log_file: Optional[Path] = None,
    format_string: str = LOG_FORMAT,
) -> logging.Logger:
    """
    Set up and configure a logger instance.
    
    Args:
        name: Logger name (typically the application name or module name)
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path to write logs to
        format_string: Log message format string
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(format_string, datefmt=DATE_FORMAT)
    
    # Console handler - always add
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler - optional
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    # Prevent propagation to root logger
    logger.propagate = False
    
    return logger


# Create the main application logger
logger = setup_logger(
    name="sparkth",
    level=logging.INFO,
)


def get_logger(name: str) -> logging.Logger:
    """
    Get a child logger with the given name.
    
    This creates a logger that inherits from the main sparkth logger,
    allowing for module-specific logging while maintaining consistent
    configuration.
    
    Args:
        name: Logger name (typically __name__ of the calling module)
        
    Returns:
        Logger instance
        
    Example:
        ```python
        from app.core.logger import get_logger
        
        logger = get_logger(__name__)
        logger.info("This is a log message")
        ```
    """
    return logging.getLogger(f"sparkth.{name}")


def set_log_level(level: int) -> None:
    """
    Set the logging level for the main logger.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    logger.setLevel(level)
    for handler in logger.handlers:
        handler.setLevel(level)


# Export commonly used logging levels for convenience
DEBUG = logging.DEBUG
INFO = logging.INFO
WARNING = logging.WARNING
ERROR = logging.ERROR
CRITICAL = logging.CRITICAL
