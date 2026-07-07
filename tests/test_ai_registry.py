"""Tests for ProviderRegistry registration and resolution."""
from __future__ import annotations

from jarvis.ai.registry import ProviderRegistry
from jarvis.ai.providers.mock_provider import MockAIProvider


def test_registry_register_and_get() -> None:
    reg = ProviderRegistry()
    reg.register("mock", lambda: MockAIProvider())
    assert "mock" in reg.available()
    prov = reg.get("mock")
    assert isinstance(prov, MockAIProvider)
