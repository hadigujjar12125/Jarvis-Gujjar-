"""Mock AI provider used for tests and offline development.

The MockProvider simulates streaming by yielding small chunks with short sleeps so
consumers can test streaming behavior and backpressure handling.
"""
from __future__ import annotations

import asyncio
from typing import AsyncIterator, Sequence

from jarvis.ai.registry import BaseAIProvider


class MockAIProvider(BaseAIProvider):
    def __init__(self, name: str = "mock", default_model: str | None = None) -> None:
        super().__init__(name, default_model=default_model)

    async def _astream_chat(self, prompt: str, context: Sequence[str]) -> AsyncIterator[str]:
        text = f"[mock response to: {prompt}]"
        # yield word by word
        for w in text.split():
            await asyncio.sleep(0.01)
            yield w + " "
