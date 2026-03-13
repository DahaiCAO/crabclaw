"""HTTP connection pool for Crabclaw."""

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, Callable

import httpx
from loguru import logger


@dataclass
class PoolConfig:
    """Configuration for HTTP connection pool."""
    max_connections: int = 100
    max_keepalive_connections: int = 20
    keepalive_expiry: float = 30.0
    timeout: float = 30.0
    connect_timeout: float = 5.0
    read_timeout: float = 30.0
    pool_limits: httpx.Limits | None = None


class HTTPClientPool:
    """Pooled HTTP client for efficient connections."""

    _instance = None

    def __new__(cls, config: PoolConfig | None = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, config: PoolConfig | None = None):
        if self._initialized:
            return

        self._config = config or PoolConfig()
        self._client: httpx.AsyncClient | None = None
        self._lock = asyncio.Lock()
        self._initialized = True

    async def get_client(self) -> httpx.AsyncClient:
        """Get or create the pooled HTTP client."""
        if self._client is None:
            async with self._lock:
                if self._client is None:
                    self._client = await self._create_client()
        return self._client

    async def _create_client(self) -> httpx.AsyncClient:
        """Create a new HTTP client with connection pooling."""
        limits = self._config.pool_limits or httpx.Limits(
            max_connections=self._config.max_connections,
            max_keepalive_connections=self._config.max_keepalive_connections,
            keepalive_expiry=self._config.keepalive_expiry,
        )

        timeout = httpx.Timeout(
            connect=self._config.connect_timeout,
            read=self._config.read_timeout,
            write=None,
            pool=self._config.timeout,
        )

        client = httpx.AsyncClient(
            limits=limits,
            timeout=timeout,
            http2=True,
        )

        logger.info(
            "Created HTTP client pool: max_connections={}, max_keepalive={}",
            self._config.max_connections,
            self._config.max_keepalive_connections,
        )

        return client

    async def request(
        self,
        method: str,
        url: str,
        **kwargs: Any
    ) -> httpx.Response:
        """Make an HTTP request using the pooled client."""
        client = await self.get_client()
        return await client.request(method, url, **kwargs)

    async def get(self, url: str, **kwargs: Any) -> httpx.Response:
        """Make a GET request."""
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        """Make a POST request."""
        return await self.request("POST", url, **kwargs)

    async def put(self, url: str, **kwargs: Any) -> httpx.Response:
        """Make a PUT request."""
        return await self.request("PUT", url, **kwargs)

    async def delete(self, url: str, **kwargs: Any) -> httpx.Response:
        """Make a DELETE request."""
        return await self.request("DELETE", url, **kwargs)

    async def close(self) -> None:
        """Close the HTTP client and release connections."""
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.info("Closed HTTP client pool")

    @property
    def is_healthy(self) -> bool:
        """Check if the client is healthy."""
        return self._client is not None and not self._client.is_closed


class RateLimiter:
    """Rate limiter for API calls."""

    def __init__(self, rate: float, burst: int = 1):
        self._rate = rate
        self._burst = burst
        self._tokens = float(burst)
        self._last_update = asyncio.get_event_loop().time()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Acquire a token, waiting if necessary."""
        async with self._lock:
            while self._tokens < 1:
                await self._refill()
                await asyncio.sleep(0.01)
            self._tokens -= 1

    async def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_update
        self._tokens = min(self._burst, self._tokens + elapsed * self._rate)
        self._last_update = now

    @asynccontextmanager
    async def limited(self):
        """Context manager for rate-limited operations."""
        await self.acquire()
        yield


class RetryPolicy:
    """Retry policy for failed requests."""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        retryable_statuses: tuple[int, ...] = (429, 500, 502, 503, 504),
    ):
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._max_delay = max_delay
        self._exponential_base = exponential_base
        self._retryable_statuses = retryable_statuses

    async def execute(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """Execute a function with retry logic."""
        last_exception = None

        for attempt in range(self._max_retries + 1):
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < self._max_retries and self._is_retryable(e):
                    delay = self._calculate_delay(attempt)
                    logger.warning(
                        "Request failed (attempt {}/{}), retrying in {}s: {}",
                        attempt + 1,
                        self._max_retries,
                        delay,
                        str(e),
                    )
                    await asyncio.sleep(delay)
                else:
                    raise

        raise last_exception

    def _is_retryable(self, error: Exception) -> bool:
        """Check if an error is retryable."""
        if isinstance(error, httpx.HTTPStatusError):
            return error.response.status_code in self._retryable_statuses
        if isinstance(error, (httpx.ConnectError, httpx.TimeoutException)):
            return True
        return False

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay with exponential backoff and jitter."""
        import random
        delay = min(self._base_delay * (self._exponential_base ** attempt), self._max_delay)
        jitter = random.uniform(0, 0.1 * delay)
        return delay + jitter


http_pool = HTTPClientPool()


__all__ = [
    "PoolConfig",
    "HTTPClientPool",
    "RateLimiter",
    "RetryPolicy",
    "http_pool",
]
