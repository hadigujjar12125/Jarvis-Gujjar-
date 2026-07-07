"""Orchestrator wiring: register EventBus, Settings, MemoryStore, and AI provider registry.

This updates the startup sequence to initialize and register the memory system so plugins
can resolve it during their start(). The orchestrator also ensures the autosave task is
started and stopped as part of the lifecycle.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

from jarvis.core.infrastructure.event_bus import EventBus
from jarvis.core.infrastructure.plugin_manager import PluginManager
from jarvis.core.infrastructure.service_registry import ServiceRegistry
from jarvis.utils.logger import get_logger
from config.settings import load_settings
from jarvis.memory import create_default_json_store
from jarvis.ai.registry import ProviderRegistry


class JarvisOrchestrator:
    """Orchestrates startup and shutdown of core JARVIS services."""

    def __init__(self) -> None:
        self._logger = get_logger(__name__)
        self._loop = asyncio.get_event_loop()
        self.settings = load_settings()
        self.event_bus = EventBus(loop=self._loop)
        self.registry = ServiceRegistry()
        self.plugin_manager = PluginManager()
        self._stopped = asyncio.Event()
        self._memory_store = None
        self._ai_registry = None

    async def start(self) -> None:
        """Start core services and plugins."""
        self._logger.info("Starting Jarvis orchestrator", assistant=self.settings.assistant_name)

        # Register core services in the registry
        await self.registry.register("event_bus", self.event_bus)
        await self.registry.register("settings", self.settings)

        # Initialize and register memory store so plugins can resolve it during start
        repo_root = Path(__file__).resolve().parents[2]
        data_dir = repo_root / "jarvis" / "data"
        memory_store = create_default_json_store(data_dir)
        # Pass event_bus to memory so it can emit events
        try:
            await memory_store.load()
            await memory_store.start_autosave()
        except Exception:
            self._logger.exception("Failed to initialize memory store")

        await self.registry.register("memory", memory_store)
        self._memory_store = memory_store

        # Initialize AI provider registry and register it
        self._ai_registry = ProviderRegistry()
        await self.registry.register("ai_registry", self._ai_registry)

        # Start plugins
        try:
            await self.plugin_manager.start_all(self.registry)
        except Exception:
            self._logger.exception("Failed during plugin startup")

        self._logger.info("Jarvis started")

    async def stop(self) -> None:
        """Stop plugins and perform cleanup.

        This method is idempotent and safe to call multiple times.
        """
        self._logger.info("Stopping Jarvis orchestrator")
        try:
            await self.plugin_manager.stop_all()
        except Exception:
            self._logger.exception("Error while stopping plugins")

        # Stop memory autosave and persist memory
        if self._memory_store is not None:
            try:
                await self._memory_store.stop_autosave()
                await self._memory_store.save()
            except Exception:
                self._logger.exception("Error while stopping memory store")

        self._stopped.set()
        self._logger.info("Jarvis stopped")

    def run(self) -> None:
        """Run the orchestrator until stopped (KeyboardInterrupt triggers shutdown).

        This is a small convenience wrapper that runs start() and waits for stop signal.
        """
        async def _main() -> None:
            await self.start()
            # Wait until stop() signals the event
            await self._stopped.wait()

        try:
            self._loop.run_until_complete(_main())
        except KeyboardInterrupt:
            self._logger.info("KeyboardInterrupt received, shutting down")
            try:
                self._loop.run_until_complete(self.stop())
            finally:
                # allow loop to close cleanly
                pass


# Simple CLI entrypoint
async def _async_main() -> None:
    orchestrator = JarvisOrchestrator()
    await orchestrator.start()
    # Block until stopped
    await orchestrator._stopped.wait()


def main() -> None:
    orchestrator = JarvisOrchestrator()
    orchestrator.run()


if __name__ == "__main__":
    main()
