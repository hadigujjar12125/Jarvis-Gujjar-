"""Integration tests for the memory store verifying event emission and service registry integration."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from jarvis.core.infrastructure.event_bus import Event
from jarvis.core.infrastructure.event_bus import EventBus
from jarvis.core.infrastructure.service_registry import ServiceRegistry
from jarvis.memory import create_default_json_store


@pytest.mark.asyncio
async def test_memory_registered_and_events(tmp_path: Path) -> None:
    bus = EventBus()
    sr = ServiceRegistry()
    await sr.register("event_bus", bus)

    data_dir = tmp_path / "data"
    store = create_default_json_store(data_dir, autosave_interval=0.1, event_bus=bus)

    # Register memory in service registry
    await sr.register("memory", store)

    # subscribe to memory events
    events = []

    async def on_any(evt: Event) -> None:
        events.append((evt.name, evt.payload))

    await bus.subscribe(Event, on_any, background=True)

    await store.load()
    await store.put("x", 1)
    await store.save()

    # allow background event handling
    await asyncio.sleep(0.05)

    # Expect at least memory.loaded, memory.put, memory.saved events
    names = [n for n, _ in events]
    assert "memory.loaded" in names
    assert "memory.put" in names
    assert "memory.saved" in names
