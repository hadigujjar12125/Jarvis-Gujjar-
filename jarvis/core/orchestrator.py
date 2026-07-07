"""Main orchestrator that wires core services and manages lifecycle.

The orchestrator builds the EventBus and ServiceRegistry, registers core services,
loads plugins, and provides a simple run loop with graceful shutdown.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from jarvis.core.infrastructure.event_bus import EventBus
from jarvis.core.infrastructure.plugin_manager import PluginManager
from jarvis.core.infrastructure.service_registry import ServiceRegistry
from jarvis.utils.logger import get_logger
from config.settings import load_settings


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

    async def start(self) -> None:
        """Start core services and plugins."""
        self._logger.info("Starting Jarvis orchestrator", assistant=self.settings.assistant_name)

        # Register core services in the registry
        await self.registry.register("event_bus", self.event_bus)
        await self.registry.register("settings", self.settings)

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
