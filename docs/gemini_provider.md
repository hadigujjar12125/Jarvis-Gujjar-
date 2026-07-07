"""Gemini provider documentation.

This document explains how the GeminiProvider works, configuration, and how to register
it with the ProviderRegistry.

Configuration
- GEMINI_API_KEY: read from environment or .env (do not store keys in code)
- GEMINI_MODEL: optional default model name

Usage
- Create a GeminiProvider factory via create_gemini_provider_factory(memory=memory, event_bus=bus)
- Register the factory with the ProviderRegistry

Example
    from jarvis.ai.providers.gemini_provider import create_gemini_provider_factory
    factory = create_gemini_provider_factory(memory=memory_store, event_bus=event_bus)
    provider_registry.register("gemini", factory)

Notes
- The provider supports streaming and emits ai.streaming.* events to the EventBus.
- By default it will attempt to initialize the official Gemini SDK lazily if no client
  is provided. For deterministic behavior and for unit tests, pass an explicit client
  implementing `async def stream_chat(prompt, model=None) -> AsyncIterator[str]`.
- The provider persists conversation transcripts to the memory store under the
  key "conversations" when available.
"""
