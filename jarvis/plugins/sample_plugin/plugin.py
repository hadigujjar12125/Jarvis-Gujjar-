"""Updated sample plugin that stores the registry reference during start and uses it during stop.

This fixes the earlier bug where `registry` was referenced but not stored on the instance.
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
        self._registry: Any | None = None

    async def start(self, registry: Any) -> None:
        self._logger.info("SamplePlugin starting")
        self._registry = registry
        try:
            event_bus = await registry.resolve("event_bus")
        except KeyError:
            self._logger.warning("EventBus not available in registry; SamplePlugin will be passive")
            return

        async def _on_event(evt: Event) -> None:
            self._logger.info("SamplePlugin received event", event=evt.name, payload=evt.payload)

        self._handler = _on_event
        # subscribe with low priority and as background so it doesn't block
        await event_bus.subscribe(Event, self._handler, priority=-10, background=True)
        self._registered = True

    async def stop(self) -> None:
        self._logger.info("SamplePlugin stopping")
        if self._registered and self._handler and self._registry is not None:
            # Unsubscribe if possible
            try:
                event_bus = await self._registry.resolve("event_bus")
                await event_bus.unsubscribe(Event, self._handler)
            except Exception:
                # registry not available at shutdown
                self._logger.exception("Failed to unsubscribe during stop")
        # short delay to simulate cleanup
        await asyncio.sleep(0.01)


def SamplePluginFactory() -> SamplePlugin:  # pragma: no cover - convenience factory
    return SamplePlugin()
