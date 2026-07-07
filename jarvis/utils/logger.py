"""Utility helpers for logging configuration used across the project.

This provides a simple, safe logging setup that creates a rotating file handler
and a console handler. Modules should call `get_logger(__name__)` to obtain
their logger instance.
"""
from __future__ import annotations

import logging
import logging.handlers
import os
from pathlib import Path
from typing import Optional

LOG_DIR = Path(__file__).resolve().parents[3] / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def _configure_root_logger(level: int = logging.INFO) -> None:
    """Configure the root logger once.

    This function is idempotent and will not reconfigure handlers if they're already set.
    """
    root = logging.getLogger()
    if root.handlers:
        return

    root.setLevel(level)

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(level)
    ch.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    root.addHandler(ch)

    # Rotating file handler
    fh = logging.handlers.RotatingFileHandler(
        LOG_DIR / "jarvis.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    fh.setLevel(level)
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    root.addHandler(fh)


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Return a configured logger for `name`.

    The log level is read from the JARVIS_LOG_LEVEL environment variable if present.
    """
    level_str = os.environ.get("LOG_LEVEL") or os.environ.get("JARVIS_LOG_LEVEL") or "INFO"
    try:
        level = getattr(logging, level_str.upper())
    except Exception:
        level = logging.INFO

    _configure_root_logger(level=level)
    return logging.getLogger(name)
