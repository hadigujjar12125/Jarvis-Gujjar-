"""AI provider design and integration doc.

This document explains the provider architecture and how to add new providers.

Key points:
- Providers implement the IAIProvider protocol: async def stream_chat(prompt, context) -> AsyncIterator[str]
  and async def chat(prompt, context) -> str.
- Register providers with ProviderRegistry.register(name, factory). The factory should
  construct a provider instance, reading any required credentials from environment variables
  or configuration. Do NOT hardcode API keys in code.
- The orchestrator registers a ProviderRegistry instance in the ServiceRegistry under
  the name 'ai_registry'. Consumers can resolve it and request providers by name.
- Example providers to add later: GeminiProvider, OpenAIProvider, ClaudeProvider, OllamaProvider,
  LocalModelProvider. Each will subclass BaseAIProvider and implement `_astream_chat`.
"""
