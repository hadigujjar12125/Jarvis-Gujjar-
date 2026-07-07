"""Gemini AI provider implementation.

This provider uses a pluggable client to communicate with the Gemini API. In production
it is recommended to pass a client implemented by the official Gemini SDK (e.g. `google.generativeai`)
that supports streaming. For unit testing and offline development a lightweight fake client
can be injected.

Configuration / environment variables:
- GEMINI_API_KEY: API key for Gemini (read from .env or environment)
- GEMINI_MODEL: model id to use (optional; default configured in ProviderConfig or GEMINI_MODEL)

Notes:
- The provider supports streaming responses and integrates with the memory store (if provided)
  by appending a conversation entry when a chat finishes.
- Events are published to the EventBus: ai.streaming.start, ai.streaming.token, ai.streaming.finish, ai.streaming.error
- The provider implements automatic retries using the BaseAIProvider retry policy.

"""
from __future__ import annotations

import os
import asyncio
from typing import AsyncIterator, Sequence, Optional, Any

from jarvis.ai.providers.base import BaseAIProvider, ProviderConfig
from jarvis.ai.providers.exceptions import ProviderUnavailable, AIProviderError
from jarvis.core.ai_types import AIChunk
from jarvis.utils.logger import get_logger


class GeminiProvider(BaseAIProvider):
    """Gemini provider that delegates to a low-level client capable of streaming.

    The `client` argument must provide an asynchronous streaming method. The provider
    will attempt to use `client.stream_chat(prompt, model=..., **kwargs)` if present; if
    not, it will look for `client.stream` or other idioms. For simplicity, clients used
    in tests are expected to implement `async def stream_chat(prompt, model=None, **kw) -> AsyncIterator[str]`.
    """

    def __init__(
        self,
        name: str = "gemini",
        config: ProviderConfig | None = None,
        event_bus: object | None = None,
        memory: object | None = None,
        client: Any | None = None,
    ) -> None:
        super().__init__(name, config=config, event_bus=event_bus)
        self._logger = get_logger(__name__)
        # Configuration via env or provided config
        self.api_key = os.getenv("GEMINI_API_KEY")
        # allow override from ProviderConfig.model
        self.model = (config.model if config and config.model else os.getenv("GEMINI_MODEL"))
        self._client = client
        self._memory = memory

        # If no client provided, attempt to lazily initialize using the Gemini SDK when used.
        if self._client is None:
            # Do not fail at construction; fail later with ProviderUnavailable when actual calls attempted
            self._logger.debug("No Gemini client provided; will attempt to use SDK at call time")

    async def _astream_chat(self, prompt: str, context: Sequence[str]) -> AsyncIterator[AIChunk]:
        # ensure client is available
        if self._client is None:
            # Try to import and configure official SDK
            try:
                # Attempt to import google.generativeai (common Gemini SDK package)
                import google.generativeai as genai  # type: ignore

                if self.api_key:
                    try:
                        genai.configure(api_key=self.api_key)
                    except Exception:
                        # Not all SDK versions use configure(); tolerate failure
                        self._logger.debug("genai.configure failed or not required; continuing")
                self._client = genai
            except Exception as exc:  # pragma: no cover - rare runtime environment
                self._logger.exception("Gemini SDK is not available and no client was provided")
                raise ProviderUnavailable("Gemini SDK not available; provide a client or install the SDK") from exc

        # The client is expected to provide an async streaming iterator of text segments.
        # To support different SDKs, attempt several common call patterns.
        stream_iter = None
        # prefer an explicit stream_chat coroutine
        if hasattr(self._client, "stream_chat"):
            try:
                stream_iter = self._client.stream_chat(prompt, model=self.model)
            except TypeError:
                # maybe requires kwargs style
                stream_iter = self._client.stream_chat(prompt, model=self.model)
        elif hasattr(self._client, "chat") and hasattr(self._client.chat, "stream"):
            # Example: genai.chat.stream(...) returns an iterator
            try:
                stream_iter = self._client.chat.stream(model=self.model, messages=[{"content": prompt}])
            except Exception as exc:  # pragma: no cover - defensive
                self._logger.exception("Failed to call client.chat.stream", exc=exc)
                raise AIProviderError("Gemini client call failed") from exc
        elif callable(self._client):
            # If client is a callable factory that can produce a streaming iterator
            try:
                stream_iter = self._client(prompt, model=self.model)
            except Exception as exc:  # pragma: no cover - defensive
                self._logger.exception("Callable client raised during invocation", exc=exc)
                raise AIProviderError("Gemini client invocation failed") from exc
        else:
            self._logger.error("Gemini client has no known streaming interface")
            raise ProviderUnavailable("Provided Gemini client does not support streaming")

        # At this point stream_iter is expected to be an async iterator yielding text segments
        if stream_iter is None:
            self._logger.error("Unable to create streaming iterator from client")
            raise ProviderUnavailable("Unable to stream from Gemini client")

        # Emit start event
        if self.config.stream_to_event_bus and self._event_bus is not None:
            try:
                await self._event_bus.publish(type(self)._make_event("ai.streaming.start", {"provider": self.name}))
            except Exception:
                self._logger.exception("Failed to publish ai.streaming.start event")

        token_index = 0
        collected_parts: list[str] = []

        # If the stream iterator is synchronous (rare), adapt it
        try:
            # Try async iteration
            async for part in stream_iter:
                # Normalize part to string if provider yields complex objects
                if isinstance(part, dict):
                    text = part.get("text") or part.get("delta") or str(part)
                else:
                    text = str(part)

                token_index += 1
                collected_parts.append(text)
                chunk = AIChunk(text=text, delta_type="token", token_index=token_index)

                # Publish token event
                if self.config.stream_to_event_bus and self._event_bus is not None:
                    try:
                        await self._event_bus.publish(type(self)._make_event("ai.streaming.token", {"provider": self.name, "text": text, "token_index": token_index}))
                    except Exception:
                        self._logger.exception("Failed to publish ai.streaming.token event")

                yield chunk
        except Exception as exc:
            self._logger.exception("Error while streaming from Gemini client", exc=exc)
            # emit error event
            if self.config.stream_to_event_bus and self._event_bus is not None:
                try:
                    await self._event_bus.publish(type(self)._make_event("ai.streaming.error", {"provider": self.name, "error": str(exc)}))
                except Exception:
                    self._logger.exception("Failed to publish ai.streaming.error event")
            raise

        # When stream completes, optionally store conversation
        full_text = "".join(collected_parts)
        # store into memory under conversations list if memory provided
        if self._memory is not None:
            try:
                # append conversation entry to conversations
                existing = await self._memory.get("conversations") or []
                if not isinstance(existing, list):
                    existing = []
                entry = {"assistant": full_text, "prompt": prompt}
                existing.append(entry)
                await self._memory.put("conversations", existing)
                # optionally save immediately
                await self._memory.save()
            except Exception:
                self._logger.exception("Failed to persist conversation to memory")

        # Emit finish event
        if self.config.stream_to_event_bus and self._event_bus is not None:
            try:
                await self._event_bus.publish(type(self)._make_event("ai.streaming.finish", {"provider": self.name, "text": full_text}))
            except Exception:
                self._logger.exception("Failed to publish ai.streaming.finish event")

        # Finalize by yielding finish token (BaseAIProvider will also yield a finish chunk; duplicates are acceptable)
        return


# Convenience factory used by ProviderRegistry registration. This factory reads configuration
# from environment variables; no API keys are hardcoded.
def create_gemini_provider_factory(memory: object | None = None, event_bus: object | None = None, config: ProviderConfig | None = None):
    def factory() -> GeminiProvider:
        return GeminiProvider(name="gemini", config=config, event_bus=event_bus, memory=memory, client=None)

    return factory
