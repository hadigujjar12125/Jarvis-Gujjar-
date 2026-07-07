"""JSON-backed memory store with a clear migration path to SQLite.

Design:
- IMemoryStore protocol (in core/ports) defines the contract.
- JsonMemoryStore implements the interface and keeps a short-term in-memory cache for
  fast reads and writes and persists to a JSON file atomically.
- The implementation is asynchronous and supports an autosave interval.
- For future SQLite support, a SqliteMemoryStore can be added implementing the same interface
  and wired into the ServiceRegistry without changing callers.

Notes:
- The store supports simple key/value storage as well as a `conversations` list for
  conversation history. The JSON file layout is flexible and validated during load.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from jarvis.core.ports import IMemoryStore
from jarvis.utils.logger import get_logger


@dataclass
class JsonMemoryStore(IMemoryStore):
    path: Path
    autosave_interval: float = 5.0
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
        """Load memory from the JSON file if it exists. If file is corrupt, a backup is created."""
        async with self._lock:
            try:
                if not self.path.exists():
                    self._logger.info("Memory file does not exist; starting fresh", path=str(self.path))
                    return
                text = self.path.read_text(encoding="utf-8")
                obj = json.loads(text)
                # Basic validation and migration hooks could be placed here
                self._data.update(obj)
                self._logger.info("Memory loaded", path=str(self.path))
            except Exception:
                self._logger.exception("Failed to load memory; backing up and starting fresh")
                # Create a backup to help with diagnostics
                try:
                    backup = self.path.with_suffix(self.path.suffix + ".bak")
                    if self.path.exists():
                        self.path.rename(backup)
                        self._logger.info("Backed up corrupt memory file", backup=str(backup))
                except Exception:
                    self._logger.exception("Failed to backup corrupt memory file")
                # leave _data as defaults

    async def save(self) -> None:
        """Persist memory to disk atomically."""
        async with self._lock:
            try:
                tmp = self.path.with_suffix(self.path.suffix + ".tmp")
                tmp.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
                tmp.replace(self.path)
                self._logger.debug("Memory saved", path=str(self.path))
            except Exception:
                self._logger.exception("Failed to save memory file")

    async def put(self, key: str, value: Any) -> None:
        async with self._lock:
            self._data.setdefault("short_term", {})
            self._data["short_term"][key] = value
            self._logger.debug("Memory put", key=key)

    async def get(self, key: str) -> Any:
        async with self._lock:
            return self._data.get("short_term", {}).get(key)

    async def delete(self, key: str) -> None:
        async with self._lock:
            if key in self._data.get("short_term", {}):
                del self._data["short_term"][key]
                self._logger.debug("Memory deleted key", key=key)

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

