import logging
from logging.handlers import RotatingFileHandler
import os
import re
from typing import Any, Optional

_PASSWORD_REGEX = re.compile(r"://([^:@\s]+):([^@\s]+)@")


def mask_url(url: Any) -> str:
    """
    Masks credentials in RTSP, HTTP, or other URLs to protect passwords from leaking into logs.
    Example: rtsp://admin:secret123@192.168.1.100:554/stream -> rtsp://admin:***@192.168.1.100:554/stream
    """
    if url is None:
        return ""
    if not isinstance(url, str):
        return str(url)
    return _PASSWORD_REGEX.sub(r"://\1:***@", url)


class MaskingFormatter(logging.Formatter):
    """Custom logging formatter that strips sensitive credentials from log output."""

    def format(self, record: logging.LogRecord) -> str:
        original = super().format(record)
        return mask_url(original)


_LOGGER_INITIALIZED = False


def setup_logger(
    log_dir: str = "data/logs",
    log_level: int = logging.INFO,
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5,
) -> logging.Logger:
    """
    Initializes root logger for ShopGuard AI with console and rotating file output.
    """
    global _LOGGER_INITIALIZED
    logger = logging.getLogger("ShopGuard")

    if _LOGGER_INITIALIZED:
        return logger

    logger.setLevel(log_level)
    logger.propagate = False

    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "shopguard.log")

    formatter = MaskingFormatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s.%(module)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)
    logger.addHandler(console_handler)

    # Rotating file handler
    try:
        file_handler = RotatingFileHandler(
            log_file, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(log_level)
        logger.addHandler(file_handler)
    except Exception as e:
        logger.warning(f"Failed to create file logger at {log_file}: {e}")

    _LOGGER_INITIALIZED = True
    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Returns a logger namespaced under ShopGuard."""
    if not _LOGGER_INITIALIZED:
        setup_logger()
    if name:
        return logging.getLogger(f"ShopGuard.{name}")
    return logging.getLogger("ShopGuard")
