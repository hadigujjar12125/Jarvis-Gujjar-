"""Unit tests for the JsonMemoryStore to verify basic persistence and operations."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from jarvis.memory.store import JsonMemoryStore


@pytest.mark.asyncio
async def test_memory_put_get(tmp_path: Path) -> None:
    path = tmp_path / "memory.json"
    store = JsonMemoryStore(path=path, autosave_interval=0.1)
    await store.put("foo", {"bar": 1})
    val = await store.get("foo")
    assert val == {"bar": 1}

    await store.save()
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["short_term"]["foo"]["bar"] == 1


@pytest.mark.asyncio
async def test_autosave_task(tmp_path: Path) -> None:
    path = tmp_path / "memory.json"
    store = JsonMemoryStore(path=path, autosave_interval=0.05)
    await store.put("a", 1)
    await store.start_autosave()
    # allow one autosave cycle
    await asyncio.sleep(0.12)
    await store.stop_autosave()
    assert path.exists()
