"""Plugin system for Crabclaw."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable

from loguru import logger


class PluginType(Enum):
    CHANNEL = "channel"
    PROVIDER = "provider"
    TOOL = "tool"
    SKILL = "skill"
    MIDDLEWARE = "middleware"


@dataclass
class PluginMetadata:
    """Metadata for a plugin."""
    name: str
    version: str
    description: str = ""
    author: str = ""
    plugin_type: PluginType = PluginType.TOOL
    dependencies: list[str] = field(default_factory=list)
    config_schema: dict | None = None


class Plugin(ABC):
    """Base class for all plugins."""

    def __init__(self, metadata: PluginMetadata):
        self._metadata = metadata
        self._enabled = False
        self._config: dict | None = None

    @property
    def metadata(self) -> PluginMetadata:
        return self._metadata

    @property
    def name(self) -> str:
        return self._metadata.name

    @property
    def enabled(self) -> bool:
        return self._enabled

    @abstractmethod
    async def initialize(self, config: dict) -> None:
        """Initialize the plugin with configuration."""
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        """Clean up plugin resources."""
        pass

    def enable(self) -> None:
        """Enable the plugin."""
        self._enabled = True
        logger.info("Enabled plugin: {}", self.name)

    def disable(self) -> None:
        """Disable the plugin."""
        self._enabled = False
        logger.info("Disabled plugin: {}", self.name)

    def validate_config(self, config: dict) -> bool:
        """Validate plugin configuration."""
        return True


class PluginLifecycle:
    """Handler for plugin lifecycle events."""

    def __init__(self):
        self._on_load: list[Callable[[Plugin], None]] = []
        self._on_unload: list[Callable[[Plugin], None]] = []
        self._on_enable: list[Callable[[Plugin], None]] = []
        self._on_disable: list[Callable[[Plugin], None]] = []

    def on_load(self, callback: Callable[[Plugin], None]) -> None:
        self._on_load.append(callback)

    def on_unload(self, callback: Callable[[Plugin], None]) -> None:
        self._on_unload.append(callback)

    def on_enable(self, callback: Callable[[Plugin], None]) -> None:
        self._on_enable.append(callback)

    def on_disable(self, callback: Callable[[Plugin], None]) -> None:
        self._on_disable.append(callback)

    async def notify_load(self, plugin: Plugin) -> None:
        for callback in self._on_load:
            callback(plugin)

    async def notify_unload(self, plugin: Plugin) -> None:
        for callback in self._on_unload:
            callback(plugin)

    async def notify_enable(self, plugin: Plugin) -> None:
        for callback in self._on_enable:
            callback(plugin)

    async def notify_disable(self, plugin: Plugin) -> None:
        for callback in self._on_disable:
            callback(plugin)


class PluginRegistry:
    """Registry for managing plugins."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._plugins: dict[str, Plugin] = {}
            cls._instance._plugin_classes: dict[str, type[Plugin]] = {}
            cls._instance._lifecycle = PluginLifecycle()
        return cls._instance

    def register(self, plugin_class: type[Plugin], metadata: PluginMetadata | None = None) -> None:
        """Register a plugin class."""
        if metadata is None:
            metadata = PluginMetadata(
                name=plugin_class.__name__,
                version="1.0.0",
                description=plugin_class.__doc__ or ""
            )
        self._plugin_classes[metadata.name] = plugin_class
        logger.info("Registered plugin class: {}", metadata.name)

    def register_instance(self, plugin: Plugin) -> None:
        """Register a plugin instance."""
        self._plugins[plugin.name] = plugin
        logger.info("Registered plugin instance: {}", plugin.name)

    def get(self, name: str) -> Plugin | None:
        """Get a plugin by name."""
        return self._plugins.get(name)

    def get_all(self) -> list[Plugin]:
        """Get all registered plugins."""
        return list(self._plugins.values())

    def get_by_type(self, plugin_type: PluginType) -> list[Plugin]:
        """Get all plugins of a specific type."""
        return [p for p in self._plugins.values() if p.metadata.plugin_type == plugin_type]

    def get_enabled(self) -> list[Plugin]:
        """Get all enabled plugins."""
        return [p for p in self._plugins.values() if p.enabled]

    async def load_plugin(self, name: str, config: dict) -> Plugin:
        """Load and initialize a plugin."""
        if name in self._plugins:
            logger.warning("Plugin {} already loaded", name)
            return self._plugins[name]

        if name not in self._plugin_classes:
            raise ValueError(f"Plugin class {name} not found")

        plugin_class = self._plugin_classes[name]
        plugin = plugin_class(self._plugin_classes.get(name, PluginMetadata(name=name, version="1.0.0")))

        await plugin.initialize(config)
        plugin.enable()

        self._plugins[name] = plugin
        await self._lifecycle.notify_load(plugin)

        return plugin

    async def unload_plugin(self, name: str) -> None:
        """Unload a plugin."""
        if name not in self._plugins:
            logger.warning("Plugin {} not loaded", name)
            return

        plugin = self._plugins[name]
        await plugin.shutdown()
        await self._lifecycle.notify_unload(plugin)

        del self._plugins[name]
        logger.info("Unloaded plugin: {}", name)

    async def enable_plugin(self, name: str) -> None:
        """Enable a plugin."""
        plugin = self.get(name)
        if plugin:
            plugin.enable()
            await self._lifecycle.notify_enable(plugin)

    async def disable_plugin(self, name: str) -> None:
        """Disable a plugin."""
        plugin = self.get(name)
        if plugin:
            plugin.disable()
            await self._lifecycle.notify_disable(plugin)

    @property
    def lifecycle(self) -> PluginLifecycle:
        return self._lifecycle


class PluginLoader:
    """Dynamic plugin loader for discovering and loading plugins."""

    def __init__(self, plugin_dir: Path | None = None):
        self._plugin_dir = plugin_dir
        self._loaded_modules: set[str] = set()

    def discover_plugins(self, plugin_dir: Path | None = None) -> list[str]:
        """Discover available plugins in the plugin directory."""
        dir_path = plugin_dir or self._plugin_dir
        if not dir_path or not dir_path.exists():
            return []

        plugins = []
        for file in dir_path.glob("*.py"):
            if file.stem.startswith("_"):
                continue
            plugins.append(file.stem)

        return plugins

    async def load_from_directory(self, plugin_dir: Path) -> list[Plugin]:
        """Load all plugins from a directory."""
        import importlib.util
        loaded = []

        for plugin_file in plugin_dir.glob("*.py"):
            if plugin_file.stem.startswith("_"):
                continue

            spec = importlib.util.spec_from_file_location(plugin_file.stem, plugin_file)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                for name in dir(module):
                    obj = getattr(module, name)
                    if isinstance(obj, type) and issubclass(obj, Plugin) and obj is not Plugin:
                        metadata = PluginMetadata(
                            name=obj.__name__,
                            version="1.0.0",
                            description=obj.__doc__ or ""
                        )
                        plugin = obj(metadata)
                        await plugin.initialize({})
                        plugin.enable()
                        loaded.append(plugin)

        return loaded


plugin_registry = PluginRegistry()


def plugin(metadata: PluginMetadata):
    """Decorator to register a plugin class."""
    def decorator(cls: type[Plugin]) -> type[Plugin]:
        plugin_registry.register(cls, metadata)
        return cls
    return decorator


__all__ = [
    "PluginType",
    "PluginMetadata",
    "Plugin",
    "PluginLifecycle",
    "PluginRegistry",
    "PluginLoader",
    "plugin_registry",
    "plugin",
]
