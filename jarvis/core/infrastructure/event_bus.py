"""Core infrastructure: async EventBus for JARVIS.

Design:
- Typed Event base class; events are dataclasses.
- EventBus supports subscribe/unsubscribe and publish.
- Handlers are async callables accepting an Event.
- Exceptions raised by handlers are caught and logged; they do not stop other handlers.
- Publish waits for all handlers to be scheduled and gathers their results with a timeout.

This module follows SOLID principles: single responsibility (event routing), dependency injection friendly,
and is fully async for responsiveness.
"""
from __future__ import annotations

import asyncio
import dataclasses
import logging
from datetime import datetime
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Optional,
    Type,
)

from jarvis.utils.logger import get_logger

Handler = Callable[["Event"], Awaitable[None]]


@dataclasses.dataclass
class Event:
    """Base event for the EventBus.

    Attributes:
        name: short name of the event type
        payload: optional dictionary payload
        timestamp: event creation timestamp (UTC)
    """

    name: str
    payload: Optional[Dict[str, Any]] = None
    timestamp: datetime = dataclasses.field(default_factory=lambda: datetime.utcnow())


class EventBus:
    """Simple async event bus.

    - Subscribers register handlers for a specific Event subclass or for the base Event to
      receive all events.
    - Handlers are invoked concurrently but publish awaits their completion.
    """

    def __init__(self, loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
        self._loop = loop or asyncio.get_event_loop()
        self._subscribers: Dict[Type[Event], List[Handler]] = {}
        self._logger = get_logger(__name__)

    def subscribe(self, event_type: Type[Event], handler: Handler) -> None:
        """Register a handler for a given event type.

        Args:
            event_type: subclass of Event to subscribe to.
            handler: async callable accepting the event.
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        if handler in self._subscribers[event_type]:
            self._logger.debug("Handler already subscribed", event_type=event_type)
            return
        self._subscribers[event_type].append(handler)
        self._logger.debug("Subscribed handler", event_type=event_type, handler=handler)

    def unsubscribe(self, event_type: Type[Event], handler: Handler) -> None:
        """Remove a previously registered handler. Safe to call even if not present."""
        handlers = self._subscribers.get(event_type)
        if not handlers:
            return
        try:
            handlers.remove(handler)
            self._logger.debug("Unsubscribed handler", event_type=event_type, handler=handler)
        except ValueError:
            self._logger.debug("Handler not found when unsubscribing", event_type=event_type)

    async def publish(self, event: Event, timeout: Optional[float] = 5.0) -> None:
        """Publish an event to all matching subscribers.

        Handlers for the specific event type plus handlers subscribed to the base Event
        will be invoked. Exceptions in handlers are caught and logged. The method awaits
        until all handlers complete or the optional timeout expires.

        Args:
            event: Event instance to publish.
            timeout: max seconds to wait for handlers. None means wait indefinitely.
        """
        self._logger.debug("Publishing event", event_name=event.name, payload=event.payload)
        to_call: List[Handler] = []

        # Collect handlers for direct type and base Event handlers
        event_cls = type(event)
        for etype, handlers in self._subscribers.items():
            try:
                if issubclass(event_cls, etype):
                    to_call.extend(handlers)
            except Exception:
                # Defensive - issubclass might fail for unexpected objects
                self._logger.exception("Failed to check subscriber type", etype=etype)

        if not to_call:
            self._logger.debug("No subscribers for event", event_name=event.name)
            return

        tasks = [self._loop.create_task(self._safe_invoke(h, event)) for h in to_call]

        self._logger.debug("Awaiting handler tasks", count=len(tasks))
        try:
            await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=timeout)
        except asyncio.TimeoutError:
            self._logger.warning(
                "Timeout waiting for event handlers",
                event_name=event.name,
                timeout=timeout,
            )

    async def _safe_invoke(self, handler: Handler, event: Event) -> None:
        """Invoke a handler and catch/log exceptions to avoid cancelling other handlers."""
        try:
            await handler(event)
        except Exception as exc:  # pragma: no cover - defensive logging
            self._logger.exception("Event handler raised exception", handler=handler, exc=exc)
