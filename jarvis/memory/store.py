"""JSON-backed memory store with optional EventBus integration and improved robustness.

This implementation emits events via EventBus (if provided) on load, save, put, and delete
so other modules (GUI, plugins) can react to memory changes. The store is implemented to
be replaceable by a future SqliteMemoryStore that adheres to the same IMemoryStore protocol.
"""
from __future__ import annotations

import asyncio
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from jarvis.core.ports import IMemoryStore
from jarvis.utils.logger import get_logger


@dataclass
class JsonMemoryStore(IMemoryStore):
    path: Path
    autosave_interval: float = 5.0
    event_bus: Optional[Any] = None  # avoid circular import; expecting EventBus-like object
    _data: Dict[str, Any] = None
    _lock: asyncio.Lock = None
    _autosave_task: Optional[asyncio.Task] = None
    _logger = get_logger(__name__)

    def __post_init__(self) -> None:
        if self._data is None:
            self._data = {"short_term": {}, "long_term": {}, "conversations": []}
        if self._lock is None:
            self._lock = asyncio.Lock()

    async def load(self) -> None:
        """Load memory from the JSON file if it exists. If file is corrupt, a backup is created.

        Emits: Event(name='memory.loaded', payload={'path': str(self.path)}) on success.
        """
        async with self._lock:
            try:
                if not self.path.exists():
                    self._logger.info("Memory file does not exist; starting fresh", path=str(self.path))
                    # ensure parent exists
                    self.path.parent.mkdir(parents=True, exist_ok=True)
                    # write initial structure
                    self.path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
                    return
                text = self.path.read_text(encoding="utf-8")
                obj = json.loads(text)
                if isinstance(obj, dict):
                    # merge carefully: replace top-level keys to avoid retaining stale structure
                    for k in ("short_term", "long_term", "conversations"):
                        if k in obj:
                            self._data[k] = obj[k]
                self._logger.info("Memory loaded", path=str(self.path))
                # emit event
                if self.event_bus is not None:
                    await self.event_bus.publish(
                        type(self)._make_event("memory.loaded", {"path": str(self.path)})
                    )
            except Exception:
                self._logger.exception("Failed to load memory; backing up and starting fresh")
                # Create a backup to help with diagnostics
                try:
                    backup = self.path.with_suffix(self.path.suffix + ".bak")
                    if self.path.exists():
                        shutil.copy2(self.path, backup)
                        self._logger.info("Backed up corrupt memory file", backup=str(backup))
                except Exception:
                    self._logger.exception("Failed to backup corrupt memory file")
                # leave _data as defaults

    async def save(self) -> None:
        """Persist memory to disk atomically.

        Emits: Event(name='memory.saved', payload={'path': str(self.path)}) on success.
        """
        async with self._lock:
            try:
                tmp = self.path.with_suffix(self.path.suffix + ".tmp")
                tmp.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
                # Atomic replace
                tmp.replace(self.path)
                self._logger.debug("Memory saved", path=str(self.path))
                if self.event_bus is not None:
                    await self.event_bus.publish(type(self)._make_event("memory.saved", {"path": str(self.path)}))
            except Exception:
                self._logger.exception("Failed to save memory file")

    async def put(self, key: str, value: Any) -> None:
        async with self._lock:
            self._data.setdefault("short_term", {})
            self._data["short_term"][key] = value
            self._logger.debug("Memory put", key=key)
            if self.event_bus is not None:
                await self.event_bus.publish(type(self)._make_event("memory.put", {"key": key}))

    async def get(self, key: str) -> Any:
        async with self._lock:
            return self._data.get("short_term", {}).get(key)

    async def delete(self, key: str) -> None:
        async with self._lock:
            if key in self._data.get("short_term", {}):
                del self._data["short_term"][key]
                self._logger.debug("Memory deleted key", key=key)
                if self.event_bus is not None:
                    await self.event_bus.publish(type(self)._make_event("memory.delete", {"key": key}))

    async def start_autosave(self) -> None:
        """Start background autosave task.

        The task will periodically call save(). Call stop_autosave() during shutdown.
        """
        if self._autosave_task:
            return

        async def _loop() -> None:
            self._logger.info("Memory autosave started", interval=self.autosave_interval)
            try:
                while True:
                    await asyncio.sleep(self.autosave_interval)
                    await self.save()
            except asyncio.CancelledError:
                self._logger.info("Memory autosave cancelled")
                raise

        self._autosave_task = asyncio.create_task(_loop())

    async def stop_autosave(self) -> None:
        if self._autosave_task:
            self._autosave_task.cancel()
            try:
                await self._autosave_task
            except asyncio.CancelledError:
                pass
            self._autosave_task = None

    @staticmethod
    def _make_event(name: str, payload: Optional[Dict[str, Any]] = None) -> "object":
        """Helper to create a plain Event-like object compatible with EventBus publish.

        We avoid importing Event directly to reduce coupling; EventBus.publish accepts
        any object that follows the Event dataclass shape (has name/payload/timestamp).
        """
        # Minimal duck-typed object
        class _E:
            def __init__(self, name: str, payload: Optional[Dict[str, Any]] = None) -> None:
                self.name = name
                self.payload = payload
                self.timestamp = None

            def cancel(self) -> None:  # no-op for memory events
                pass

        return _E(name, payload)
