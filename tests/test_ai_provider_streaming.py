"""Tests for AI provider streaming behavior and retry policy."""
from __future__ import annotations

import asyncio

import pytest

from jarvis.ai.providers.mock_provider import MockAIProvider
from jarvis.ai.providers.base import AIProviderError


@pytest.mark.asyncio
async def test_mock_streaming_chunks() -> None:
    prov = MockAIProvider()
    chunks = []
    async for c in prov.stream_chat("hello"):
        chunks.append(c)
    # last chunk should be finish
    assert chunks[-1].delta_type == "finish"
    text = "".join([c.text for c in chunks if c.delta_type == "token"])  # type: ignore
    assert "mock response to" in text


@pytest.mark.asyncio
async def test_mock_retries_then_success() -> None:
    prov = MockAIProvider(fail_times=2)
    # stream_chat should retry internally and eventually raise only if exceeds retries
    with pytest.raises(AIProviderError):
        # configure retry policy to 1 attempt for quick test
        prov.retry_policy.max_attempts = 1
        async for _ in prov.stream_chat("hello"):
            pass

    # Now with sufficient attempts it should succeed
    prov = MockAIProvider(fail_times=2)
    prov.retry_policy.max_attempts = 3
    chunks = []
    async for c in prov.stream_chat("hello"):
        chunks.append(c)
    assert chunks and chunks[-1].delta_type == "finish"
