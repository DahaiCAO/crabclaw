"""Dependency injection container for nanobot."""

from contextlib import asynccontextmanager
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, TypeVar, Generic, Type

from loguru import logger


T = TypeVar("T")


class Lifetime(Enum):
    """Service lifetime options."""
    TRANSIENT = "transient"
    SINGLETON = "singleton"
    SCOPED = "scoped"


@dataclass
class ServiceDescriptor:
    """Descriptor for a registered service."""
    service_type: type
    implementation: type | object
    lifetime: Lifetime
    factory: Callable | None = None


class Container:
    """Dependency injection container."""

    def __init__(self):
        self._services: dict[type, ServiceDescriptor] = {}
        self._singletons: dict[type, Any] = {}
        self._scoped_instances: dict[type, Any] = {}

    def register(
        self,
        service_type: Type[T],
        implementation: Type[T] | None = None,
        lifetime: Lifetime = Lifetime.TRANSIENT,
    ) -> "Container":
        """Register a service."""
        impl = implementation or service_type
        self._services[service_type] = ServiceDescriptor(
            service_type=service_type,
            implementation=impl,
            lifetime=lifetime,
        )
        logger.debug("Registered service: {} -> {} ({})", service_type, impl, lifetime)
        return self

    def register_instance(self, service_type: Type[T], instance: T) -> "Container":
        """Register an existing instance as a singleton."""
        self._services[service_type] = ServiceDescriptor(
            service_type=service_type,
            implementation=type(instance),
            lifetime=Lifetime.SINGLETON,
        )
        self._singletons[service_type] = instance
        logger.debug("Registered instance: {}", service_type)
        return self

    def register_factory(
        self,
        service_type: Type[T],
        factory: Callable[["Container"], T],
        lifetime: Lifetime = Lifetime.TRANSIENT,
    ) -> "Container":
        """Register a factory function for creating instances."""
        self._services[service_type] = ServiceDescriptor(
            service_type=service_type,
            implementation=type(factory()),
            lifetime=lifetime,
            factory=factory,
        )
        logger.debug("Registered factory: {}", service_type)
        return self

    def resolve(self, service_type: Type[T]) -> T:
        """Resolve a service instance."""
        if service_type not in self._services:
            raise KeyError(f"Service {service_type} not registered")

        descriptor = self._services[service_type]

        if descriptor.lifetime == Lifetime.SINGLETON:
            if service_type in self._singletons:
                return self._singletons[service_type]
            instance = self._create_instance(descriptor)
            self._singletons[service_type] = instance
            return instance

        if descriptor.lifetime == Lifetime.SCOPED:
            if service_type in self._scoped_instances:
                return self._scoped_instances[service_type]
            instance = self._create_instance(descriptor)
            self._scoped_instances[service_type] = instance
            return instance

        return self._create_instance(descriptor)

    def _create_instance(self, descriptor: ServiceDescriptor) -> Any:
        """Create a new instance of a service."""
        if descriptor.factory:
            return descriptor.factory(self)

        impl = descriptor.implementation

        try:
            init_signature = impl.__init__.__annotations__
            params = {}

            for param_name, param_type in init_signature.items():
                if param_name in ("self", "return"):
                    continue
                if param_type in self._services:
                    params[param_name] = self.resolve(param_type)

            return impl(**params)
        except Exception as e:
            logger.error("Failed to create instance of {}: {}", descriptor.service_type, e)
            raise

    @asynccontextmanager
    async def create_scope(self):
        """Create a scoped context for dependency resolution."""
        scope = ScopedContainer(self)
        try:
            yield scope
        finally:
            scope.dispose()

    def clear(self) -> None:
        """Clear all registered services."""
        self._services.clear()
        self._singletons.clear()
        self._scoped_instances.clear()


class ScopedContainer:
    """Scoped container for request-level dependencies."""

    def __init__(self, parent: Container):
        self._parent = parent
        self._instances: dict[type, Any] = {}

    def resolve(self, service_type: Type[T]) -> T:
        """Resolve a service from the scoped container."""
        if service_type in self._instances:
            return self._instances[service_type]

        descriptor = self._parent._services.get(service_type)
        if not descriptor:
            raise KeyError(f"Service {service_type} not registered")

        if descriptor.lifetime == Lifetime.SINGLETON:
            instance = self._parent.resolve(service_type)
            self._instances[service_type] = instance
            return instance

        instance = self._parent._create_instance(descriptor)
        self._instances[service_type] = instance
        return instance

    def dispose(self) -> None:
        """Dispose scoped instances."""
        for instance in self._instances.values():
            if hasattr(instance, "close"):
                import asyncio
                try:
                    asyncio.create_task(instance.close())
                except Exception:
                    pass
        self._instances.clear()


class ServiceCollection:
    """Fluent builder for service registration."""

    def __init__(self):
        self._container = Container()

    def add_singleton(self, service_type: Type[T], implementation: Type[T] | None = None) -> "ServiceCollection":
        self._container.register(service_type, implementation, Lifetime.SINGLETON)
        return self

    def add_transient(self, service_type: Type[T], implementation: Type[T] | None = None) -> "ServiceCollection":
        self._container.register(service_type, implementation, Lifetime.TRANSIENT)
        return self

    def add_scoped(self, service_type: Type[T], implementation: Type[T] | None = None) -> "ServiceCollection":
        self._container.register(service_type, implementation, Lifetime.SCOPED)
        return self

    def add_instance(self, service_type: Type[T], instance: T) -> "ServiceCollection":
        self._container.register_instance(service_type, instance)
        return self

    def build(self) -> Container:
        return self._container


def injectable(lifetime: Lifetime = Lifetime.TRANSIENT):
    """Decorator to mark a class as injectable."""
    def decorator(cls: Type[T]) -> Type[T]:
        cls._injectable = True
        cls._lifetime = lifetime
        return cls
    return decorator


container = Container()


__all__ = [
    "Lifetime",
    "ServiceDescriptor",
    "Container",
    "ScopedContainer",
    "ServiceCollection",
    "injectable",
    "container",
]
