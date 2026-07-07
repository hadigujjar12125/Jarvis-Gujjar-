"""A tiny sample plugin used by tests and as a reference implementation.

This plugin subscribes to all events and logs them. It demonstrates the plugin
start/stop lifecycle.
"""
from __future__ import annotations

import asyncio
from typing import Any

from jarvis.core.infrastructure.event_bus import Event
from jarvis.utils.logger import get_logger


class SamplePlugin:
    def __init__(self) -> None:
        self._logger = get_logger(__name__)
        self._registered = False
        self._handler = None

    async def start(self, registry: Any) -> None:
        self._logger.info("SamplePlugin starting")
        try:
            event_bus = await registry.resolve("event_bus")
        except KeyError:
            self._logger.warning("EventBus not available in registry; SamplePlugin will be passive")
            return

        async def _on_event(evt: Event) -> None:
            self._logger.info("SamplePlugin received event", event=evt.name, payload=evt.payload)

        self._handler = _on_event
        event_bus.subscribe(Event, self._handler)
        self._registered = True

    async def stop(self) -> None:
        self._logger.info("SamplePlugin stopping")
        if self._registered and self._handler:
            # Unsubscribe if possible
            try:
                event_bus = await registry.resolve("event_bus")
                event_bus.unsubscribe(Event, self._handler)
            except Exception:
                # registry not available at shutdown
                pass
        # short delay to simulate cleanup
        await asyncio.sleep(0.01)
