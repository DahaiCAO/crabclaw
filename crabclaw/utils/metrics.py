"""Metrics and monitoring for Crabclaw."""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from loguru import logger


class MetricType(Enum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


@dataclass
class Metric:
    """Base metric definition."""
    name: str
    type: MetricType
    description: str = ""
    tags: dict[str, str] = field(default_factory=dict)


@dataclass
class Counter:
    """Counter metric that only increases."""
    _value: int = 0

    def inc(self, value: int = 1) -> None:
        self._value += value

    @property
    def value(self) -> int:
        return self._value


@dataclass
class Gauge:
    """Gauge metric that can go up and down."""
    _value: float = 0.0

    def inc(self, value: float = 1.0) -> None:
        self._value += value

    def dec(self, value: float = 1.0) -> None:
        self._value -= value

    def set(self, value: float) -> None:
        self._value = value

    @property
    def value(self) -> float:
        return self._value


class Histogram:
    """Histogram metric for measuring distributions."""

    def __init__(self, buckets: list[float] | None = None):
        self._buckets = buckets or [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
        self._values: list[float] = []
        self._sum: float = 0.0
        self._count: int = 0

    def observe(self, value: float) -> None:
        self._values.append(value)
        self._sum += value
        self._count += 1

    @property
    def count(self) -> int:
        return self._count

    @property
    def sum(self) -> float:
        return self._sum

    def get_percentile(self, percentile: float) -> float:
        if not self._values:
            return 0.0
        sorted_values = sorted(self._values)
        index = int(len(sorted_values) * percentile)
        return sorted_values[min(index, len(sorted_values) - 1)]


class Timer:
    """Timer metric for measuring duration."""

    def __init__(self):
        self._histogram = Histogram()
        self._start_time: float | None = None

    def start(self) -> None:
        self._start_time = time.perf_counter()

    def stop(self) -> float:
        if self._start_time is None:
            raise ValueError("Timer not started")
        duration = time.perf_counter() - self._start_time
        self._histogram.observe(duration)
        self._start_time = None
        return duration

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    @property
    def histogram(self) -> Histogram:
        return self._histogram


class MetricsRegistry:
    """Central registry for all metrics."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._counters: dict[str, Counter] = {}
            cls._instance._gauges: dict[str, Gauge] = {}
            cls._instance._histograms: dict[str, Histogram] = {}
            cls._instance._timers: dict[str, Timer] = {}
        return cls._instance

    def counter(self, name: str, description: str = "", tags: dict[str, str] | None = None) -> Counter:
        """Get or create a counter metric."""
        key = self._make_key(name, tags)
        if key not in self._counters:
            self._counters[key] = Counter()
            logger.debug("Created counter metric: {}", name)
        return self._counters[key]

    def gauge(self, name: str, description: str = "", tags: dict[str, str] | None = None) -> Gauge:
        """Get or create a gauge metric."""
        key = self._make_key(name, tags)
        if key not in self._gauges:
            self._gauges[key] = Gauge()
            logger.debug("Created gauge metric: {}", name)
        return self._gauges[key]

    def histogram(self, name: str, buckets: list[float] | None = None, tags: dict[str, str] | None = None) -> Histogram:
        """Get or create a histogram metric."""
        key = self._make_key(name, tags)
        if key not in self._histograms:
            self._histograms[key] = Histogram(buckets)
            logger.debug("Created histogram metric: {}", name)
        return self._histograms[key]

    def timer(self, name: str, tags: dict[str, str] | None = None) -> Timer:
        """Get or create a timer metric."""
        key = self._make_key(name, tags)
        if key not in self._timers:
            self._timers[key] = Timer()
            logger.debug("Created timer metric: {}", name)
        return self._timers[key]

    def _make_key(self, name: str, tags: dict[str, str] | None = None) -> str:
        """Create a unique key for a metric."""
        if not tags:
            return name
        tag_str = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
        return f"{name}{{{tag_str}}}"

    def get_all_metrics(self) -> dict:
        """Get all metrics as a dictionary."""
        return {
            "counters": {k: v.value for k, v in self._counters.items()},
            "gauges": {k: v.value for k, v in self._gauges.items()},
            "histograms": {
                k: {"count": v.count, "sum": v.sum, "p50": v.get_percentile(0.5), "p95": v.get_percentile(0.95), "p99": v.get_percentile(0.99)}
                for k, v in self._histograms.items()
            }
        }

    def reset(self) -> None:
        """Reset all metrics (useful for testing)."""
        self._counters.clear()
        self._gauges.clear()
        self._histograms.clear()
        self._timers.clear()


metrics = MetricsRegistry()


def count(name: str, tags: dict[str, str] | None = None):
    """Decorator to count function calls."""
    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            metrics.counter(name, tags=tags).inc()
            return func(*args, **kwargs)
        return wrapper
    return decorator


def timed(name: str, tags: dict[str, str] | None = None):
    """Decorator to time function execution."""
    def decorator(func: Callable):
        def wrapper(*args, **kwargs):
            timer = metrics.timer(name, tags=tags)
            with timer:
                return func(*args, **kwargs)
        return wrapper
    return decorator


def timed_async(name: str, tags: dict[str, str] | None = None):
    """Decorator to time async function execution."""
    def decorator(func: Callable):
        import functools
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            timer = metrics.timer(name, tags=tags)
            with timer:
                return await func(*args, **kwargs)
        return wrapper
    return decorator


__all__ = [
    "MetricType",
    "Metric",
    "Counter",
    "Gauge",
    "Histogram",
    "Timer",
    "MetricsRegistry",
    "metrics",
    "count",
    "timed",
    "timed_async",
]
