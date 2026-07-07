"""Core typed interfaces (ports) for JARVIS modules.

Use typing.Protocol to define the contracts implemented by plugins and adapters.
These lightweight protocols make testing and swapping implementations straightforward.
"""
from __future__ import annotations

from typing import AsyncIterator, Protocol, Sequence, Any, Dict

from jarvis.core.infrastructure.event_bus import Event


class IPlugin(Protocol):
    """Plugin contract required by the PluginManager.

    Plugins should implement an async start(registry) method and an async stop() method.
    They may optionally expose a metadata() method returning a dict or object describing
    the plugin.
    """

    async def start(self, registry: Any) -> None:  # pragma: no cover - interface
        ...

    async def stop(self) -> None:  # pragma: no cover - interface
        ...


class IAIProvider(Protocol):
    """AI provider abstraction.

    Implementations should support streaming chat responses as an async iterator
    and a simple non-streaming chat method.
    """

    async def stream_chat(self, prompt: str, context: Sequence[str] | None = None) -> AsyncIterator[str]:
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


class ICommandExecutor(Protocol):
    async def execute(self, command_name: str, payload: Dict[str, Any] | None = None) -> Any:
        ...
