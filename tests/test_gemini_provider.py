"""Unit tests for the GeminiProvider.

These tests do not call the real Gemini API. Instead, they pass a fake client that simulates
streaming behavior so we can validate streaming, memory integration, and event emission.
"""
from __future__ import annotations

import asyncio
from typing import AsyncIterator

import pytest

from jarvis.ai.providers.gemini_provider import GeminiProvider
from jarvis.core.ai_types import AIChunk
from jarvis.core.infrastructure.event_bus import EventBus
from jarvis.memory import create_default_json_store
from pathlib import Path


class FakeClient:
    def __init__(self, parts: list[str], fail_times: int = 0, delay: float = 0.0):
        self.parts = parts
        self.fail_times = fail_times
        self._calls = 0
        self.delay = delay

    async def stream_chat(self, prompt: str, model: str | None = None) -> AsyncIterator[str]:
        self._calls += 1
        if self.fail_times and self._calls <= self.fail_times:
            raise RuntimeError("simulated transient failure")
        for p in self.parts:
            if self.delay:
                await asyncio.sleep(self.delay)
            yield p


@pytest.mark.asyncio
async def test_gemini_streaming_and_memory(tmp_path: Path) -> None:
    # Setup fake client that yields 3 parts
    client = FakeClient(["Hello", " world", "!"], delay=0)
    bus = EventBus()
    data_dir = tmp_path / "data"
    memory = create_default_json_store(data_dir)

    prov = GeminiProvider(name="gemini", config=None, event_bus=bus, memory=memory, client=client)

    # subscribe to streaming events
    events = []

    async def on_evt(evt):
        events.append((evt.name, evt.payload))

    await bus.subscribe(object, on_evt, background=True)

    # perform streaming
    collected = []
    async for chunk in prov.stream_chat("Say hi"):
        assert isinstance(chunk, AIChunk)
        if chunk.delta_type == "token":
            collected.append(chunk.text)

    assert "".join(collected) == "Hello world!"

    # memory should contain conversations
    convs = await memory.get("conversations")
    assert isinstance(convs, list)
    assert convs[-1]["assistant"] == "Hello world!"

    # events must contain start, token(s), finish
    names = [n for n, _ in events]
    assert any(n == "ai.streaming.start" for n in names)
    assert any(n == "ai.streaming.token" for n in names)
    assert any(n == "ai.streaming.finish" for n in names)


@pytest.mark.asyncio
async def test_gemini_retries_with_transient_failure(tmp_path: Path) -> None:
    # Fake client fails twice then succeeds
    client = FakeClient(["ok"], fail_times=2)
    bus = EventBus()
    data_dir = tmp_path / "data"
    memory = create_default_json_store(data_dir)

    prov = GeminiProvider(name="gemini", config=None, event_bus=bus, memory=memory, client=client)
    # configure retry policy
    prov.retry_policy.max_attempts = 3

    parts = []
    async for c in prov.stream_chat("hi"):
        if c.delta_type == "token":
            parts.append(c.text)

    assert "".join(parts) == "ok"


@pytest.mark.asyncio
async def test_gemini_no_client_raises(tmp_path: Path) -> None:
    prov = GeminiProvider(name="gemini", config=None, event_bus=None, memory=None, client=None)
    # If SDK not installed and no client is provided, streaming should raise ProviderUnavailable
    with pytest.raises(Exception):
        async for _ in prov.stream_chat("hi"):
            pass
