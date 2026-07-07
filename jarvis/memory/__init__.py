"""Memory package init and helper functions."""
from __future__ import annotations

from pathlib import Path

from jarvis.memory.store import JsonMemoryStore


def create_default_json_store(data_dir: Path, autosave_interval: float = 5.0) -> JsonMemoryStore:
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / "memory.json"
    return JsonMemoryStore(path=path, autosave_interval=autosave_interval)
