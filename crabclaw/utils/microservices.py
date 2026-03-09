"""Microservices infrastructure for nanobot."""

import asyncio
import signal
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from loguru import logger


class ServiceStatus(Enum):
    STARTING = "starting"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    STOPPING = "stopping"
    STOPPED = "stopped"


@dataclass
class ServiceHealth:
    """Health status of a service."""
    status: ServiceStatus = ServiceStatus.STARTING
    checks: dict[str, bool] = field(default_factory=dict)
    message: str = ""
    metadata: dict = field(default_factory=dict)


class Service(ABC):
    """Base class for microservices."""

    def __init__(self, name: str):
        self._name = name
        self._health = ServiceHealth()
        self._running = False

    @property
    def name(self) -> str:
        return self._name

    @property
    def health(self) -> ServiceHealth:
        return self._health

    @property
    def is_running(self) -> bool:
        return self._running

    @abstractmethod
    async def start(self) -> None:
        """Start the service."""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop the service."""
        pass

    @abstractmethod
    async def check_health(self) -> ServiceHealth:
        """Check service health."""
        pass


class ServiceRegistry:
    """Registry for service discovery."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._services: dict[str, Service] = {}
            cls._instance._lock = asyncio.Lock()
        return cls._instance

    async def register(self, service: Service) -> None:
        """Register a service."""
        async with self._lock:
            self._services[service.name] = service
            logger.info("Registered service: {}", service.name)

    async def unregister(self, name: str) -> None:
        """Unregister a service."""
        async with self._lock:
            if name in self._services:
                del self._services[name]
                logger.info("Unregistered service: {}", name)

    def get(self, name: str) -> Service | None:
        """Get a service by name."""
        return self._services.get(name)

    def get_all(self) -> list[Service]:
        """Get all registered services."""
        return list(self._services.values())

    async def get_healthy_services(self) -> list[Service]:
        """Get all healthy services."""
        healthy = []
        for service in self._services.values():
            health = await service.check_health()
            if health.status == ServiceStatus.HEALTHY:
                healthy.append(service)
        return healthy


class HealthChecker:
    """Health checker for services."""

    def __init__(self):
        self._checks: dict[str, Callable[[], bool]] = {}

    def register_check(self, name: str, check: Callable[[], bool]) -> None:
        """Register a health check."""
        self._checks[name] = check

    async def run_checks(self) -> dict[str, bool]:
        """Run all health checks."""
        results = {}
        for name, check in self._checks.items():
            try:
                if asyncio.iscoroutinefunction(check):
                    results[name] = await check()
                else:
                    results[name] = check()
            except Exception as e:
                logger.warning("Health check {} failed: {}", name, e)
                results[name] = False
        return results


class LifecycleManager:
    """Manager for service lifecycle events."""

    def __init__(self):
        self._on_startup: list[Callable[[], None]] = []
        self._on_shutdown: list[Callable[[], None]] = []

    def on_startup(self, callback: Callable[[], None]) -> None:
        self._on_startup.append(callback)

    def on_shutdown(self, callback: Callable[[], None]) -> None:
        self._on_shutdown.append(callback)

    async def notify_startup(self) -> None:
        for callback in self._on_startup:
            if asyncio.iscoroutinefunction(callback):
                await callback()
            else:
                callback()

    async def notify_shutdown(self) -> None:
        for callback in self._on_shutdown:
            if asyncio.iscoroutinefunction(callback):
                await callback()
            else:
                callback()


class GracefulShutdown:
    """Handler for graceful shutdown."""

    def __init__(self, timeout: float = 30.0):
        self._timeout = timeout
        self._shutdown_event = asyncio.Event()
        self._services: list[Service] = []
        self._lock = asyncio.Lock()

    async def add_service(self, service: Service) -> None:
        async with self._lock:
            self._services.append(service)

    async def shutdown(self) -> None:
        logger.info("Starting graceful shutdown...")
        self._shutdown_event.set()

        async with self._lock:
            for service in self._services:
                try:
                    await asyncio.wait_for(
                        service.stop(),
                        timeout=self._timeout / len(self._services)
                    )
                    logger.info("Service {} stopped", service.name)
                except asyncio.TimeoutError:
                    logger.warning("Service {} stop timed out", service.name)
                except Exception as e:
                    logger.error("Error stopping service {}: {}", service.name, e)

        logger.info("Graceful shutdown complete")

    def is_shutting_down(self) -> bool:
        return self._shutdown_event.is_set()


class SignalHandler:
    """Handler for OS signals."""

    def __init__(self):
        self._shutdown: GracefulShutdown | None = None

    def setup(self, shutdown: GracefulShutdown) -> None:
        self._shutdown = shutdown

        def signal_handler(sig, frame):
            logger.info("Received signal: {}", sig)
            if self._shutdown:
                asyncio.create_task(self._shutdown.shutdown())

        if hasattr(signal, "SIGINT"):
            signal.signal(signal.SIGINT, signal_handler)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, signal_handler)


service_registry = ServiceRegistry()
lifecycle_manager = LifecycleManager()
graceful_shutdown = GracefulShutdown()


@asynccontextmanager
async def service_context(services: list[Service]):
    """Context manager for service lifecycle."""
    try:
        for service in services:
            await service.start()
            await service_registry.register(service)

        await lifecycle_manager.notify_startup()

        yield
    finally:
        await lifecycle_manager.notify_shutdown()

        for service in reversed(services):
            await service_registry.unregister(service.name)
            await service.stop()


__all__ = [
    "ServiceStatus",
    "ServiceHealth",
    "Service",
    "ServiceRegistry",
    "HealthChecker",
    "LifecycleManager",
    "GracefulShutdown",
    "SignalHandler",
    "service_registry",
    "lifecycle_manager",
    "graceful_shutdown",
    "service_context",
]
