"""Improved PluginManager with version validation, dependency checks and enable/disable support.

Manifest structure (plugin.json):
{
  "id": "plugin_id",
  "name": "Human-readable name",
  "version": "1.2.3",
  "entry_point": "module.path:Attr",
  "enabled": true,
  "requires": [
      { "id": "other_plugin", "min_version": "1.0.0" }
  ]
}

The manager will:
- Discover manifests under the plugins/ directory.
- Validate version strings using packaging.version.
- Check declared dependencies against other discovered manifests and skip
  plugins with unmet dependencies.
- Respect the `enabled` flag in the manifest.
"""
from __future__ import annotations

import asyncio
import importlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from jarvis.utils.logger import get_logger
from jarvis.utils.exceptions import PluginError
from jarvis.core.infrastructure.service_registry import ServiceRegistry
from packaging.version import Version, InvalidVersion


@dataclass
class Dependency:
    id: str
    min_version: Optional[Version]


class PluginManifest:
    """Parsed plugin manifest with helpers."""

    def __init__(self, raw: Dict[str, Any], source: Path) -> None:
        self.raw = raw
        self.source = source
        self.id: str = raw.get("id") or raw.get("name")
        self.name: str = raw.get("name", self.id)
        self.version_raw: str = raw.get("version", "0.0.0")
        try:
            self.version: Version = Version(self.version_raw)
        except InvalidVersion:
            raise PluginError("Invalid plugin version", manifest=raw, source=str(source))
        self.entry_point: Optional[str] = raw.get("entry_point")
        self.enabled: bool = bool(raw.get("enabled", True))
        self.requires: List[Dependency] = []
        for r in raw.get("requires", []):
            min_v = None
            if r.get("min_version"):
                try:
                    min_v = Version(r["min_version"])
                except InvalidVersion:
                    raise PluginError("Invalid dependency version", dependency=r, source=str(source))
            self.requires.append(Dependency(id=r["id"], min_version=min_v))


class PluginManager:
    """Discover and manage plugins located under the plugins/ directory."""

    def __init__(self, plugin_dir: Optional[Path] = None) -> None:
        self._logger = get_logger(__name__)
        self.plugin_dir = plugin_dir or Path(__file__).resolve().parents[2] / "plugins"
        self._loaded: Dict[str, Any] = {}
        self._manifests: Dict[str, PluginManifest] = {}
        self._lock = asyncio.Lock()

    def discover_manifests(self) -> List[PluginManifest]:
        """Scan plugin_dir for plugin.json files and return parsed manifests."""
        manifests: List[PluginManifest] = []
        self._manifests.clear()

        if not self.plugin_dir.exists():
            self._logger.debug("Plugin directory does not exist", path=str(self.plugin_dir))
            return manifests

        for p in self.plugin_dir.rglob("plugin.json"):
            try:
                raw = json.loads(p.read_text(encoding="utf-8"))
                m = PluginManifest(raw, p)
                manifests.append(m)
                self._manifests[m.id] = m
                self._logger.debug("Found plugin manifest", path=str(p), id=m.id, version=str(m.version))
            except PluginError as exc:
                self._logger.error("Invalid plugin manifest", path=str(p), exc=exc)
            except Exception as exc:  # pragma: no cover - defensive
                self._logger.exception("Failed to read plugin manifest", path=str(p), exc=exc)
        return manifests

    def _check_dependencies(self, manifests: List[PluginManifest]) -> List[PluginManifest]:
        """Return the subset of manifests that have their dependencies satisfied and are enabled."""
        valid: List[PluginManifest] = []
        for m in manifests:
            if not m.enabled:
                self._logger.info("Skipping disabled plugin", plugin=m.id)
                continue
            unmet = False
            for dep in m.requires:
                other = self._manifests.get(dep.id)
                if other is None:
                    self._logger.error("Plugin dependency missing", plugin=m.id, dependency=dep.id)
                    unmet = True
                    break
                if dep.min_version and other.version < dep.min_version:
                    self._logger.error(
                        "Plugin dependency version too low",
                        plugin=m.id,
                        dependency=dep.id,
                        required=str(dep.min_version),
                        found=str(other.version),
                    )
                    unmet = True
                    break
            if not unmet:
                valid.append(m)
        return valid

    async def start_all(self, registry: ServiceRegistry) -> None:
        """Start all discovered plugins and register them in the local _loaded map."""
        manifests = self.discover_manifests()
        if not manifests:
            self._logger.debug("No plugins to start")
            return

        # Check dependencies and enabled flags
        manifests = self._check_dependencies(manifests)

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
                    self._logger.info("Plugin started", plugin=m.id, version=str(m.version))
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

