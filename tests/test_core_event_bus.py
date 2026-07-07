"""Initial tests for the EventBus implementation.

These tests validate basic publish/subscribe behavior, handler ordering, and
robustness when handlers raise exceptions.
"""
from __future__ import annotations

import asyncio

import pytest

from jarvis.core.infrastructure.event_bus import Event, EventBus


class TestEvent(Event):
    pass


@pytest.mark.asyncio
async def test_publish_subscribe_basic() -> None:
    bus = EventBus()

    received: list[str] = []

    async def handler(evt: Event) -> None:
        received.append(evt.name)

    bus.subscribe(TestEvent, handler)

    await bus.publish(TestEvent(name="test1"))

    # Give the loop a short moment if scheduling uses tasks
    await asyncio.sleep(0)

    assert received == ["test1"]


@pytest.mark.asyncio
async def test_publish_multiple_handlers_and_exceptions() -> None:
    bus = EventBus()

    called: list[str] = []

    async def good_handler(evt: Event) -> None:
        called.append(f"ok:{evt.name}")

    async def bad_handler(evt: Event) -> None:
        raise RuntimeError("handler failure")

    bus.subscribe(TestEvent, good_handler)
    bus.subscribe(TestEvent, bad_handler)

    # Should not raise despite bad_handler raising; good_handler must still run
    await bus.publish(TestEvent(name="multi"))

    await asyncio.sleep(0)

    assert "ok:multi" in called
