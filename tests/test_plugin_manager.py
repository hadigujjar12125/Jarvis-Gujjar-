"""Updated plugin manager tests to assert that disabled plugins and plugins with unmet dependencies are not loaded."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from jarvis.core.infrastructure.plugin_manager import PluginManager
from jarvis.core.infrastructure.service_registry import ServiceRegistry


@pytest.mark.asyncio
async def test_plugin_manager_start_stop() -> None:
    project_root = Path(__file__).resolve().parents[1]
    plugin_dir = project_root / "jarvis" / "plugins"
    pm = PluginManager(plugin_dir=plugin_dir)
    sr = ServiceRegistry()
    # register a minimal event_bus placeholder so the sample plugin can resolve it
    await sr.register("event_bus", object())

    # Start all should not raise
    await pm.start_all(sr)

    # The disabled plugin should not be loaded
    assert "disabled_plugin" not in pm._loaded
    # The plugin with missing dependency should not be loaded
    assert "needs_missing_dep" not in pm._loaded

    # Stop all should not raise
    await pm.stop_all()
