"""Simple service registry / dependency container used by core and plugins.

This is intentionally lightweight: registration by name with optional type checks on resolve.
It supports registering factories (callables) as well as instances.

Design goals:
- Minimal API for simplicity and testability.
- Thread / task safe for typical asyncio usage.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Dict, Optional, Type, TypeVar

from jarvis.utils.logger import get_logger

T = TypeVar("T")


class ServiceRegistry:
    """A tiny dependency registry for services and factories."""

    def __init__(self) -> None:
        self._services: Dict[str, Any] = {}
        self._lock = asyncio.Lock()
        self._logger = get_logger(__name__)

    async def register(self, name: str, instance: Any) -> None:
        """Register a service instance or factory under `name`.

        If a service is already registered with the same name it will be overwritten.
        """
        async with self._lock:
            self._services[name] = instance
            self._logger.debug("Service registered", name=name, instance=instance)

    async def resolve(self, name: str, expected_type: Optional[Type[T]] = None) -> T:
        """Resolve a previously registered service by name.

        Args:
            name: service name
            expected_type: optional type to assert the returned service is compatible with.

        Returns:
            The registered service instance.

        Raises:
            KeyError: if the service is not found.
            TypeError: if the resolved service does not match expected_type.
        """
        async with self._lock:
            if name not in self._services:
                self._logger.error("Service not found", name=name)
                raise KeyError(f"Service '{name}' is not registered")
            instance = self._services[name]

        # If the registered value is a factory (callable), call it to obtain the instance.
        if callable(instance) and not isinstance(instance, type):
            try:
                resolved = instance()
            except Exception as exc:  # pragma: no cover - defensive
                self._logger.exception("Factory raised during resolve", name=name, exc=exc)
                raise
        else:
            resolved = instance

        if expected_type and not isinstance(resolved, expected_type):
            self._logger.error("Resolved service has unexpected type", name=name, expected=expected_type, actual=type(resolved))
            raise TypeError(f"Service '{name}' is not of expected type {expected_type}")

        self._logger.debug("Service resolved", name=name, instance=resolved)
        return resolved

    async def unregister(self, name: str) -> None:
        """Unregister a service if present."""
        async with self._lock:
            if name in self._services:
                del self._services[name]
                self._logger.debug("Service unregistered", name=name)

    async def contains(self, name: str) -> bool:
        """Return True if a service is registered under `name`."""
        async with self._lock:
            return name in self._services
