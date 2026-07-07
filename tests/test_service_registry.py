"""Tests for the ServiceRegistry to ensure registration and resolution work as expected."""
from __future__ import annotations

import pytest
import asyncio
from jarvis.core.infrastructure.service_registry import ServiceRegistry


@pytest.mark.asyncio
async def test_register_and_resolve_instance() -> None:
    sr = ServiceRegistry()
    await sr.register("x", 123)
    val = await sr.resolve("x")
    assert val == 123


@pytest.mark.asyncio
async def test_register_factory_and_resolve() -> None:
    sr = ServiceRegistry()

    def factory() -> str:
        return "hello"

    await sr.register("f", factory)
    val = await sr.resolve("f")
    assert val == "hello"


@pytest.mark.asyncio
async def test_resolve_missing_raises() -> None:
    sr = ServiceRegistry()
    with pytest.raises(KeyError):
        await sr.resolve("not_found")
