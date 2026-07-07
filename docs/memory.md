"""Memory module documentation.

This document describes the JsonMemoryStore implementation and the IMemoryStore contract.

Key points:
- Public API (IMemoryStore): load(), save(), put(key,value), get(key), delete(key),
  start_autosave(), stop_autosave(). These are async methods.
- The JsonMemoryStore persists data into a file (memory.json) atomically and supports a
  background autosave task. It also emits events via EventBus when key actions occur.
- For future SQLite support: implement a SqliteMemoryStore adhering to IMemoryStore and
  register it in the ServiceRegistry under the name "memory". No callers need to change.
"""
