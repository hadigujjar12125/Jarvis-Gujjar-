"""Common exceptions used across the JARVIS codebase."""

from __future__ import annotations


class JarvisError(Exception):
    """Base exception for JARVIS-specific errors."""


class PluginError(JarvisError):
    """Raised for plugin discovery/load/runtime errors."""

    def __init__(self, message: str, **context: object) -> None:
        super().__init__(message)
        self.context = context
