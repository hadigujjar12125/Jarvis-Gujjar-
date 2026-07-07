"""Tests for the AI provider registry and MockAIProvider streaming behavior."""
from __future__ import annotations

import asyncio

import pytest

from jarvis.ai.registry import ProviderRegistry
from jarvis.ai.providers.mock_provider import MockAIProvider


@pytest.mark.asyncio
async def test_mock_provider_streaming() -> None:
    prov = MockAIProvider()
    parts = []
    async for p in prov.stream_chat("hello"):  # type: ignore[arg-type]
        parts.append(p)
    assert parts
    assert "mock response" in "".join(parts)


def test_provider_registry_registration() -> None:
    reg = ProviderRegistry()
    reg.register("mock", lambda: MockAIProvider())
    assert "mock" in reg.available()
    prov = reg.get("mock")
    assert isinstance(prov, MockAIProvider)
