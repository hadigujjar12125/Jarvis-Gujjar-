"""Core ports (protocols) used by the system.

This module defines the contracts implemented by adapters and providers. The
IAIProvider interface returns streaming `AIChunk` objects for rich token-level
semantics.
"""
from __future__ import annotations

from typing import AsyncIterator, Protocol, Sequence, Any, Dict

from jarvis.core.ai_types import AIChunk


class IPlugin(Protocol):
    async def start(self, registry: Any) -> None:  # pragma: no cover - interface
        ...

    async def stop(self) -> None:  # pragma: no cover - interface
        ...


class IAIProvider(Protocol):
    """AI provider abstraction.

    Implementations should support streaming chat responses as an async iterator
    yielding AIChunk objects and a simple non-streaming chat method.
    """

    async def stream_chat(self, prompt: str, context: Sequence[str] | None = None) -> AsyncIterator[AIChunk]:
        ...

    async def chat(self, prompt: str, context: Sequence[str] | None = None) -> str:
        ...


class IVoiceService(Protocol):
    async def start_listening(self) -> None:
        ...

    async def stop_listening(self) -> None:
        ...

    async def speak(self, text: str) -> None:
        ...


class IMemoryStore(Protocol):
    async def load(self) -> None:
        ...

    async def save(self) -> None:
        ...

    async def put(self, key: str, value: Any) -> None:
        ...

    async def get(self, key: str) -> Any:
        ...

    async def delete(self, key: str) -> None:
        ...


class ICommandExecutor(Protocol):
    async def execute(self, command_name: str, payload: Dict[str, Any] | None = None) -> Any:
        ...
