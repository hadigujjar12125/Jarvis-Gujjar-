"""Example showing how to stream tokens from a provider and subscribe to EventBus tokens.

Run this example after starting the orchestrator or ensure an EventBus is available.
"""
import asyncio
from jarvis.ai.providers.mock_provider import MockAIProvider
from jarvis.core.infrastructure.event_bus import EventBus


async def main() -> None:
    bus = EventBus()

    async def on_token(evt):
        print("EVENT BUS TOKEN:", evt.payload)

    await bus.subscribe(object, on_token, background=True)

    prov = MockAIProvider()
    async for chunk in prov.stream_chat("Hello world"):
        print("CHUNK:", chunk)


if __name__ == "__main__":
    asyncio.run(main())
