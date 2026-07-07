"""Enhanced EventBus with priorities, cancellation, background handlers, and optional history.

Features:
- Handlers can be registered with a priority (higher values run first) and as background.
- Non-background handlers are awaited sequentially in priority order; if an event is cancelled by
  a handler calling event.cancel(), further non-background handlers are skipped.
- Background handlers are scheduled as tasks and do not block the publish call unless
  publish(..., wait_for_background=True) is used.
- Optional in-memory event history (ring buffer) can be enabled to record recent events.

Design decisions:
- Sequential invocation for non-background handlers simplifies cancellation semantics and
  makes ordered processing deterministic.
- Background handlers are fire-and-forget by default to avoid blocking the caller. They are
  still supervised by logging for exceptions.
"""
from __future__ import annotations

import asyncio
import dataclasses
from collections import deque
from datetime import datetime
from typing import (
    Any,
    Awaitable,
    Callable,
    Deque,
    Dict,
    List,
    Optional,
    Tuple,
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
        priority: integer priority for the event itself (higher = more important)
    """

    name: str
    payload: Optional[Dict[str, Any]] = None
    timestamp: datetime = dataclasses.field(default_factory=lambda: datetime.utcnow())
    priority: int = 0

    # internal cancellation flag
    _cancelled: bool = dataclasses.field(default=False, init=False, repr=False)

    def cancel(self) -> None:
        """Mark this event as cancelled. Further non-background handlers will not run."""
        self._cancelled = True

    @property
    def cancelled(self) -> bool:
        return self._cancelled


class _Subscriber:
    """Internal representation of a subscriber with metadata."""

    def __init__(self, handler: Handler, priority: int = 0, background: bool = False) -> None:
        self.handler = handler
        self.priority = priority
        self.background = background


class EventBus:
    """Async event bus supporting priorities, cancellation, background handlers, and history.

    Usage:
        bus = EventBus(history_size=200)
        bus.subscribe(MyEvent, handler, priority=10, background=False)
        await bus.publish(MyEvent(name="..."))
    """

    def __init__(self, loop: Optional[asyncio.AbstractEventLoop] = None, history_size: int = 0) -> None:
        self._loop = loop or asyncio.get_event_loop()
        self._subscribers: Dict[Type[Event], List[_Subscriber]] = {}
        self._logger = get_logger(__name__)
        self._history_enabled = history_size > 0
        self._history: Optional[Deque[Event]] = deque(maxlen=history_size) if self._history_enabled else None
        self._lock = asyncio.Lock()

    async def subscribe(
        self, event_type: Type[Event], handler: Handler, priority: int = 0, background: bool = False
    ) -> None:
        """Register a handler for a given event type.

        Args:
            event_type: subclass of Event to subscribe to.
            handler: async callable accepting the event.
            priority: handler priority. Higher priority handlers execute earlier.
            background: if True the handler runs in the background (scheduled task) and does
                        not block the publisher by default.
        """
        async with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            subs = self._subscribers[event_type]
            for s in subs:
                if s.handler == handler:
                    self._logger.debug("Handler already subscribed", event_type=event_type)
                    return
            subs.append(_Subscriber(handler, priority=priority, background=background))
            # Keep list sorted by priority desc for deterministic order
            subs.sort(key=lambda s: s.priority, reverse=True)
            self._logger.debug("Subscribed handler", event_type=event_type, handler=handler, priority=priority, background=background)

    async def unsubscribe(self, event_type: Type[Event], handler: Handler) -> None:
        """Remove a previously registered handler. Safe to call even if not present."""
        async with self._lock:
            handlers = self._subscribers.get(event_type)
            if not handlers:
                return
            before = len(handlers)
            handlers[:] = [s for s in handlers if s.handler != handler]
            after = len(handlers)
            if before != after:
                self._logger.debug("Unsubscribed handler", event_type=event_type, handler=handler)

    async def publish(self, event: Event, timeout: Optional[float] = 5.0, wait_for_background: bool = False) -> None:
        """Publish an event to all matching subscribers.

        Behavior:
        - Non-background handlers are invoked sequentially in order of handler priority.
          If a handler sets event.cancel(), subsequent non-background handlers are skipped.
        - Background handlers are scheduled as tasks. If wait_for_background is True,
          publish will await their completion (with the same timeout behavior).

        Args:
            event: Event instance to publish.
            timeout: max seconds to wait for handlers; applies to awaited handlers.
            wait_for_background: whether to also wait for background handlers to finish.
        """
        self._logger.debug("Publishing event", event_name=event.name, payload=event.payload, priority=event.priority)

        if self._history_enabled and self._history is not None:
            # store a shallow copy to avoid mutation issues
            try:
                self._history.append(event)
            except Exception:
                self._logger.exception("Failed to append event to history")

        # Collect subscribers matching the event type
        to_call: List[_Subscriber] = []
        async with self._lock:
            event_cls = type(event)
            for etype, subs in self._subscribers.items():
                try:
                    if issubclass(event_cls, etype):
                        to_call.extend(subs)
                except Exception:
                    self._logger.exception("Failed to check subscriber type", etype=etype)

        if not to_call:
            self._logger.debug("No subscribers for event", event_name=event.name)
            return

        # Separate background and foreground handlers
        fg_handlers = [s for s in to_call if not s.background]
        bg_handlers = [s for s in to_call if s.background]

        # Execute foreground handlers sequentially honoring priority
        try:
            for s in fg_handlers:
                if event.cancelled:
                    self._logger.debug("Event cancelled; skipping remaining handlers", event_name=event.name)
                    break
                coro = s.handler(event)
                task = self._loop.create_task(coro)
                try:
                    await asyncio.wait_for(task, timeout=timeout)
                except asyncio.TimeoutError:
                    self._logger.warning("Timeout in event handler", event_name=event.name, handler=s.handler, timeout=timeout)
                except Exception:
                    self._logger.exception("Exception in event handler", handler=s.handler)
        except Exception:
            self._logger.exception("Unexpected error while running foreground handlers")

        # Schedule background handlers
        bg_tasks: List[asyncio.Task] = []
        for s in bg_handlers:
            t = self._loop.create_task(self._safe_background_invoke(s.handler, event))
            bg_tasks.append(t)

        if wait_for_background and bg_tasks:
            try:
                await asyncio.wait_for(asyncio.gather(*bg_tasks, return_exceptions=True), timeout=timeout)
            except asyncio.TimeoutError:
                self._logger.warning("Timeout waiting for background handlers", event_name=event.name, timeout=timeout)

    async def _safe_background_invoke(self, handler: Handler, event: Event) -> None:
        """Run a background handler and log exceptions."""
        try:
            await handler(event)
        except Exception:
            self._logger.exception("Background event handler raised exception", handler=handler)

    def get_history(self) -> List[Event]:
        """Return a list copy of recent events (if history enabled), newest last."""
        if not self._history_enabled or self._history is None:
            raise RuntimeError("Event history not enabled")
        return list(self._history)

