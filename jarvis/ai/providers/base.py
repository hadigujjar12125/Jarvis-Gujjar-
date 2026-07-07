"""Base classes and utilities for AI providers.

This module defines the BaseAIProvider which provides common functionality such as
chat collection, retry policy, and optional EventBus publishing of streaming tokens.
Provider implementations should subclass BaseAIProvider and implement `_astream_chat`.
"""
from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from typing import AsyncIterator, Callable, Dict, Iterable, List, Optional, Sequence

from jarvis.core.ai_types import AIChunk
from jarvis.utils.logger import get_logger
from jarvis.utils.exceptions import JarvisError


class AIProviderError(JarvisError):
    pass


@dataclass
class RetryPolicy:
    max_attempts: int = 3
    base_delay: float = 0.5
    max_delay: float = 10.0
    jitter: float = 0.1

    def next_delay(self, attempt: int) -> float:
        """Return an exponential backoff delay with jitter for the given attempt (1-based)."""
        exp = min(self.base_delay * (2 ** (attempt - 1)), self.max_delay)
        jitter = random.uniform(-self.jitter, self.jitter) * exp
        return max(0.0, exp + jitter)


@dataclass
class ProviderConfig:
    model: Optional[str] = None
    timeout: Optional[float] = 30.0
    max_tokens: Optional[int] = None
    stream_to_event_bus: bool = True


class BaseAIProvider:
    """Base class for AI providers offering helpers for streaming and retries.

    Providers must implement `_astream_chat` which yields AIChunk objects.
    """

    def __init__(self, name: str, config: ProviderConfig | None = None, event_bus: object | None = None) -> None:
        self.name = name
        self.config = config or ProviderConfig()
        self._logger = get_logger(f"jarvis.ai.providers.{name}")
        self._event_bus = event_bus
        self.retry_policy = RetryPolicy()

    async def stream_chat(self, prompt: str, context: Sequence[str] | None = None) -> AsyncIterator[AIChunk]:
        """Default streaming wrapper that yields chunks from `_astream_chat`.

        For streaming providers, `_astream_chat` should be implemented. This method
        will forward chunks to the EventBus as configured and yield them to callers.
        """
        context = context or []
        attempt = 0
        while True:
            attempt += 1
            try:
                async for chunk in self._astream_chat(prompt, context):
                    # forward to event bus if configured
                    if self.config.stream_to_event_bus and self._event_bus is not None:
                        try:
                            await self._event_bus.publish(
                                type(self)._make_event("ai.streaming.token", {"provider": self.name, "text": chunk.text, "token_index": chunk.token_index})
                            )
                        except Exception:
                            self._logger.exception("Failed to publish streaming token to EventBus")
                    yield chunk
                # when underlying stream completes normally, yield finish chunk
                yield AIChunk(text="", delta_type="finish")
                return
            except Exception as exc:
                self._logger.exception("Provider streaming error", exc=exc, attempt=attempt)
                if attempt >= self.retry_policy.max_attempts:
                    # emit an error chunk
                    err_chunk = AIChunk(text=str(exc), delta_type="error", metadata={"attempt": attempt})
                    if self.config.stream_to_event_bus and self._event_bus is not None:
                        try:
                            await self._event_bus.publish(type(self)._make_event("ai.streaming.error", {"provider": self.name, "error": str(exc)}))
                        except Exception:
                            self._logger.exception("Failed to publish streaming error to EventBus")
                    yield err_chunk
                    raise AIProviderError("Streaming failed after retries") from exc
                else:
                    delay = self.retry_policy.next_delay(attempt)
                    self._logger.info("Retrying provider stream", attempt=attempt, delay=delay)
                    await asyncio.sleep(delay)

    async def chat(self, prompt: str, context: Sequence[str] | None = None) -> str:
        """Convenience method to collect a full response from the streaming API with retries."""
        parts: List[str] = []
        async for chunk in self.stream_chat(prompt, context):
            if chunk.delta_type == "token":
                parts.append(chunk.text)
            elif chunk.delta_type == "error":
                self._logger.error("Error chunk received during chat", provider=self.name, error=chunk.text)
                raise AIProviderError(chunk.text)
            elif chunk.delta_type == "finish":
                break
        return "".join(parts)

    async def health_check(self) -> bool:
        """Providers may override to implement liveliness checks. Default returns True."""
        return True

    @staticmethod
    def _make_event(name: str, payload: dict) -> object:
        # Minimal duck-typed Event-like object to avoid importing Event and circular deps
        class _E:
            def __init__(self, name: str, payload: dict) -> None:
                self.name = name
                self.payload = payload
                self.timestamp = None

            def cancel(self) -> None:
                pass

        return _E(name, payload)
