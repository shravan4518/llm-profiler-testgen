"""
Centralized logging configuration for the RAG system
"""
import logging
import sys
from pathlib import Path
import config

def setup_logger(name: str) -> logging.Logger:
    """
    Setup logger with file and console handlers

    Args:
        name: Logger name (usually __name__)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, config.LOG_LEVEL))

    # Avoid duplicate handlers
    if logger.handlers:
        return logger

    # File handler
    file_handler = logging.FileHandler(config.LOG_FILE, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(config.LOG_FORMAT)
    file_handler.setFormatter(file_formatter)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, config.LOG_LEVEL))
    console_formatter = logging.Formatter('%(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)

    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
