"""Improved MockAIProvider that yields AIChunk objects and supports simulated failures for testing."""
from __future__ import annotations

import asyncio
from typing import AsyncIterator, Sequence, Optional

from jarvis.ai.providers.base import BaseAIProvider
from jarvis.core.ai_types import AIChunk


class MockAIProvider(BaseAIProvider):
    def __init__(self, name: str = "mock", default_model: str | None = None, fail_times: int = 0, delay: float = 0.01) -> None:
        super().__init__(name, config=None)
        self.fail_times = fail_times
        self._calls = 0
        self.delay = delay

    async def _astream_chat(self, prompt: str, context: Sequence[str]) -> AsyncIterator[AIChunk]:
        self._calls += 1
        if self.fail_times and self._calls <= self.fail_times:
            # simulate transient failure
            raise RuntimeError("simulated transient failure")

        text = f"mock response to: {prompt}"
        token_index = 0
        for word in text.split():
            await asyncio.sleep(self.delay)
            token_index += 1
            yield AIChunk(text=word + " ", delta_type="token", token_index=token_index)
