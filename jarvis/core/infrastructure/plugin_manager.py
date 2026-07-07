"""Plugin manager skeleton.

Responsibilities:
- Discover plugins by scanning a plugins directory for plugin.json manifests.
- Load plugin modules dynamically and instantiate plugin classes.
- Start/stop plugin lifecycle, wiring in the ServiceRegistry.

This is intentionally lightweight for the first implementation. Plugins are expected to
expose an async `start(registry)` and `stop()` API. A real product would define and type
an IPlugin protocol and validate manifests strictly.
"""
from __future__ import annotations

import asyncio
import importlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from jarvis.utils.logger import get_logger
from jarvis.utils.exceptions import PluginError
from jarvis.core.infrastructure.service_registry import ServiceRegistry


class PluginManifest:
    """Minimal manifest representation read from plugin.json."""

    def __init__(self, raw: Dict[str, Any]) -> None:
        self.id = raw.get("id") or raw.get("name")
        self.version = raw.get("version", "0.0.0")
        self.entry_point = raw.get("entry_point")  # e.g. "jarvis.plugins.my_plugin:Plugin"
        self.raw = raw


class PluginManager:
    """Discover and manage plugins located under the plugins/ directory."""

    def __init__(self, plugin_dir: Optional[Path] = None) -> None:
        self._logger = get_logger(__name__)
        self.plugin_dir = plugin_dir or Path(__file__).resolve().parents[2] / "plugins"
        self._loaded: Dict[str, Any] = {}
        self._lock = asyncio.Lock()

    def discover_manifests(self) -> List[PluginManifest]:
        """Scan plugin_dir for plugin.json files and return parsed manifests."""
        manifests: List[PluginManifest] = []
        if not self.plugin_dir.exists():
            self._logger.debug("Plugin directory does not exist", path=str(self.plugin_dir))
            return manifests

        for p in self.plugin_dir.rglob("plugin.json"):
            try:
                raw = json.loads(p.read_text(encoding="utf-8"))
                manifests.append(PluginManifest(raw))
                self._logger.debug("Found plugin manifest", path=str(p), id=raw.get("id"))
            except Exception as exc:  # pragma: no cover - defensive
                self._logger.exception("Failed to read plugin manifest", path=str(p), exc=exc)
        return manifests

    async def start_all(self, registry: ServiceRegistry) -> None:
        """Start all discovered plugins and register them in the local _loaded map."""
        manifests = self.discover_manifests()
        if not manifests:
            self._logger.debug("No plugins to start")
            return

        async with self._lock:
            for m in manifests:
                try:
                    plugin = self._load_plugin(m)
                    # plugin expected to be an object with async start(registry) method
                    if hasattr(plugin, "start"):
                        maybe_coro = plugin.start(registry)
                        if asyncio.iscoroutine(maybe_coro):
                            await maybe_coro
                    self._loaded[m.id] = plugin
                    self._logger.info("Plugin started", plugin=m.id)
                except Exception as exc:
                    self._logger.exception("Failed to start plugin", plugin=m.id, exc=exc)

    def _load_plugin(self, manifest: PluginManifest) -> Any:
        """Load plugin from manifest.entry_point.

        Entry point format: 'module.path:ClassName' or 'module.path:factory_function'
        """
        if not manifest.entry_point:
            raise PluginError("Plugin manifest missing entry_point", manifest=manifest.raw)

        try:
            module_path, attr = manifest.entry_point.split(":", 1)
        except ValueError:
            raise PluginError("Invalid entry_point format; expected 'module:attr'", entry_point=manifest.entry_point)

        try:
            module = importlib.import_module(module_path)
            factory = getattr(module, attr)
            plugin = factory() if callable(factory) else factory
            return plugin
        except Exception as exc:  # pragma: no cover - defensive
            self._logger.exception("Failed to import plugin entry point", entry_point=manifest.entry_point, exc=exc)
            raise PluginError("Failed to import plugin", entry_point=manifest.entry_point) from exc

    async def stop_all(self) -> None:
        """Stop all loaded plugins by calling stop() where present."""
        async with self._lock:
            for pid, plugin in list(self._loaded.items()):
                try:
                    if hasattr(plugin, "stop"):
                        maybe_coro = plugin.stop()
                        if asyncio.iscoroutine(maybe_coro):
                            await maybe_coro
                    self._logger.info("Plugin stopped", plugin=pid)
                except Exception:
                    self._logger.exception("Error stopping plugin", plugin=pid)
                finally:
                    self._loaded.pop(pid, None)

