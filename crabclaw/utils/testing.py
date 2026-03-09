"""Test fixtures for nanobot."""

import asyncio
from dataclasses import dataclass, field
from typing import Any

import pytest


@dataclass
class MockMessage:
    """Mock message for testing."""
    content: str
    role: str = "user"
    user_id: str = "test_user"
    channel: str = "test"
    metadata: dict = field(default_factory=dict)


@dataclass
class MockChannel:
    """Mock channel for testing."""
    name: str = "mock"
    messages: list[MockMessage] = field(default_factory=list)

    async def send(self, content: str, **kwargs: Any) -> None:
        self.messages.append(MockMessage(content=content, role="assistant"))

    async def receive(self) -> MockMessage | None:
        return self.messages.pop(0) if self.messages else None


class AsyncMock:
    """Async mock for testing."""

    def __init__(self, *args: Any, **kwargs: Any):
        self._args = args
        self._kwargs = kwargs
        self._call_count = 0

    async def __call__(self, *args: Any, **kwargs: Any):
        self._call_count += 1
        return self._args[0] if self._args else None


class FixtureBuilder:
    """Builder for creating test fixtures."""

    def __init__(self):
        self._fixtures: dict[str, Any] = {}

    def add_fixture(self, name: str, fixture: Any) -> "FixtureBuilder":
        self._fixtures[name] = fixture
        return self

    def get_fixture(self, name: str) -> Any:
        return self._fixtures.get(name)

    def build(self) -> dict[str, Any]:
        return self._fixtures.copy()


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_message():
    """Fixture for mock message."""
    return MockMessage(content="Hello, world!")


@pytest.fixture
def mock_channel():
    """Fixture for mock channel."""
    return MockChannel()


@pytest.fixture
def fixture_builder():
    """Fixture for fixture builder."""
    return FixtureBuilder()


class AsyncIteratorFixture:
    """Fixture for async iterator testing."""

    def __init__(self, items: list[Any]):
        self._items = iter(items)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._items)
        except StopIteration:
            raise StopAsyncIteration


@pytest.fixture
def async_iterator():
    """Fixture for async iterator."""
    def _create_iterator(items: list[Any]):
        return AsyncIteratorFixture(items)
    return _create_iterator


__all__ = [
    "MockMessage",
    "MockChannel",
    "AsyncMock",
    "FixtureBuilder",
    "AsyncIteratorFixture",
]
