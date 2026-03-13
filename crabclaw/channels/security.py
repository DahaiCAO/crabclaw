"""Channel security utilities for access control and rate limiting."""

import asyncio
import hashlib
import time
from dataclasses import dataclass
from typing import Any

from loguru import logger


@dataclass
class RateLimitConfig:
    """Rate limiting configuration."""
    max_requests_per_minute: int = 60
    max_requests_per_hour: int = 1000
    burst_size: int = 10
    cooldown_seconds: float = 1.0


@dataclass
class AccessAttempt:
    """Record of an access attempt."""
    timestamp: float
    sender_id: str
    allowed: bool
    reason: str | None = None


class RateLimiter:
    """Token bucket rate limiter for channel access."""

    def __init__(self, config: RateLimitConfig | None = None):
        self.config = config or RateLimitConfig()
        self._buckets: dict[str, dict] = {}
        self._lock = asyncio.Lock()

    async def is_allowed(self, sender_id: str) -> tuple[bool, str | None]:
        """
        Check if request is allowed under rate limit.

        Returns:
            Tuple of (allowed, reason)
        """
        async with self._lock:
            now = time.time()

            if sender_id not in self._buckets:
                self._buckets[sender_id] = {
                    'tokens': self.config.burst_size,
                    'last_update': now,
                    'minute_count': 0,
                    'minute_start': now,
                    'hour_count': 0,
                    'hour_start': now,
                }

            bucket = self._buckets[sender_id]

            # Update token bucket
            elapsed = now - bucket['last_update']
            tokens_to_add = elapsed / self.config.cooldown_seconds
            bucket['tokens'] = min(
                self.config.burst_size,
                bucket['tokens'] + tokens_to_add
            )
            bucket['last_update'] = now

            # Reset minute counter if needed
            if now - bucket['minute_start'] >= 60:
                bucket['minute_count'] = 0
                bucket['minute_start'] = now

            # Reset hour counter if needed
            if now - bucket['hour_start'] >= 3600:
                bucket['hour_count'] = 0
                bucket['hour_start'] = now

            # Check rate limits
            if bucket['tokens'] < 1:
                return False, "Rate limit exceeded: burst capacity exhausted"

            if bucket['minute_count'] >= self.config.max_requests_per_minute:
                return False, f"Rate limit exceeded: {self.config.max_requests_per_minute} requests per minute"

            if bucket['hour_count'] >= self.config.max_requests_per_hour:
                return False, f"Rate limit exceeded: {self.config.max_requests_per_hour} requests per hour"

            # Consume token
            bucket['tokens'] -= 1
            bucket['minute_count'] += 1
            bucket['hour_count'] += 1

            return True, None

    def get_stats(self, sender_id: str) -> dict[str, Any]:
        """Get rate limit statistics for a sender."""
        bucket = self._buckets.get(sender_id, {})
        if not bucket:
            return {
                'tokens': self.config.burst_size,
                'minute_count': 0,
                'hour_count': 0,
            }

        return {
            'tokens': bucket['tokens'],
            'minute_count': bucket['minute_count'],
            'hour_count': bucket['hour_count'],
            'minute_limit': self.config.max_requests_per_minute,
            'hour_limit': self.config.max_requests_per_hour,
        }

    def reset(self, sender_id: str | None = None) -> None:
        """Reset rate limiter for a specific sender or all senders."""
        if sender_id:
            self._buckets.pop(sender_id, None)
        else:
            self._buckets.clear()


class AccessControl:
    """Enhanced access control for channels."""

    def __init__(
        self,
        allow_from: list[str],
        rate_limit_config: RateLimitConfig | None = None,
        enable_logging: bool = True,
    ):
        self.allow_from = allow_from
        self.rate_limiter = RateLimiter(rate_limit_config)
        self.enable_logging = enable_logging
        self._access_log: list[AccessAttempt] = []
        self._max_log_size = 1000
        self._failed_attempts: dict[str, list[float]] = {}
        self._block_threshold = 5  # Block after 5 failed attempts
        self._block_duration = 300  # Block for 5 minutes

    def is_allowed(self, sender_id: str) -> tuple[bool, str | None]:
        """
        Check if sender is allowed to access the channel.

        Returns:
            Tuple of (allowed, reason)
        """
        # Check if sender is blocked due to failed attempts
        if self._is_blocked(sender_id):
            return False, "Access denied: too many failed attempts"

        # Check allow list
        if not self.allow_from:
            self._log_attempt(sender_id, False, "empty_allow_list")
            self._record_failed_attempt(sender_id)
            return False, "Access denied: no users in allow list"

        if "*" in self.allow_from:
            self._log_attempt(sender_id, True, "wildcard_allowed")
            return True, None

        sender_str = str(sender_id)
        allowed = sender_str in self.allow_from or any(
            p in self.allow_from for p in sender_str.split("|") if p
        )

        if not allowed:
            self._log_attempt(sender_id, False, "not_in_allow_list")
            self._record_failed_attempt(sender_id)
            return False, f"Access denied: sender {sender_id} not in allow list"

        self._log_attempt(sender_id, True, None)
        return True, None

    async def check_rate_limit(self, sender_id: str) -> tuple[bool, str | None]:
        """Check if sender is within rate limits."""
        return await self.rate_limiter.is_allowed(sender_id)

    def _is_blocked(self, sender_id: str) -> bool:
        """Check if sender is temporarily blocked."""
        if sender_id not in self._failed_attempts:
            return False

        now = time.time()
        attempts = self._failed_attempts[sender_id]

        # Clean old attempts
        attempts[:] = [t for t in attempts if now - t < self._block_duration]

        if len(attempts) >= self._block_threshold:
            logger.warning(
                f"Sender {sender_id} is temporarily blocked due to {len(attempts)} failed attempts"
            )
            return True

        return False

    def _record_failed_attempt(self, sender_id: str) -> None:
        """Record a failed access attempt."""
        if sender_id not in self._failed_attempts:
            self._failed_attempts[sender_id] = []

        self._failed_attempts[sender_id].append(time.time())

    def _log_attempt(self, sender_id: str, allowed: bool, reason: str | None) -> None:
        """Log access attempt."""
        if not self.enable_logging:
            return

        attempt = AccessAttempt(
            timestamp=time.time(),
            sender_id=sender_id,
            allowed=allowed,
            reason=reason,
        )

        self._access_log.append(attempt)

        # Trim log if too large
        if len(self._access_log) > self._max_log_size:
            self._access_log = self._access_log[-self._max_log_size:]

        # Log to logger
        if allowed:
            logger.debug(f"Access granted to {sender_id}")
        else:
            logger.warning(f"Access denied to {sender_id}: {reason}")

    def get_access_log(self, sender_id: str | None = None) -> list[AccessAttempt]:
        """Get access log, optionally filtered by sender."""
        if sender_id:
            return [a for a in self._access_log if a.sender_id == sender_id]
        return self._access_log.copy()

    def get_stats(self) -> dict[str, Any]:
        """Get access control statistics."""
        total_attempts = len(self._access_log)
        allowed_attempts = sum(1 for a in self._access_log if a.allowed)
        blocked_attempts = total_attempts - allowed_attempts

        return {
            'total_attempts': total_attempts,
            'allowed': allowed_attempts,
            'blocked': blocked_attempts,
            'allow_list_size': len(self.allow_from),
            'wildcard_enabled': '*' in self.allow_from,
        }

    def clear_log(self) -> None:
        """Clear access log."""
        self._access_log.clear()


class ChannelSecurityManager:
    """Manages security for all channels."""

    def __init__(self):
        self._access_controls: dict[str, AccessControl] = {}
        self._global_rate_limiter = RateLimiter(
            RateLimitConfig(
                max_requests_per_minute=120,
                max_requests_per_hour=2000,
            )
        )

    def register_channel(
        self,
        channel_name: str,
        allow_from: list[str],
        rate_limit_config: RateLimitConfig | None = None,
    ) -> None:
        """Register a channel with access control."""
        self._access_controls[channel_name] = AccessControl(
            allow_from=allow_from,
            rate_limit_config=rate_limit_config,
        )
        logger.info(f"Registered security for channel: {channel_name}")

    async def check_access(
        self,
        channel_name: str,
        sender_id: str,
    ) -> tuple[bool, str | None]:
        """
        Check if sender is allowed to access the channel.

        Returns:
            Tuple of (allowed, reason)
        """
        # Check global rate limit
        global_allowed, global_reason = await self._global_rate_limiter.is_allowed(sender_id)
        if not global_allowed:
            return False, f"Global rate limit: {global_reason}"

        # Check channel-specific access control
        access_control = self._access_controls.get(channel_name)
        if not access_control:
            logger.warning(f"No access control configured for channel: {channel_name}")
            return False, "Channel not configured"

        # Check allow list
        allowed, reason = access_control.is_allowed(sender_id)
        if not allowed:
            return False, reason

        # Check channel-specific rate limit
        rate_allowed, rate_reason = await access_control.check_rate_limit(sender_id)
        if not rate_allowed:
            return False, f"Rate limit: {rate_reason}"

        return True, None

    def get_channel_stats(self, channel_name: str) -> dict[str, Any] | None:
        """Get statistics for a channel."""
        access_control = self._access_controls.get(channel_name)
        if not access_control:
            return None

        return access_control.get_stats()

    def get_all_stats(self) -> dict[str, Any]:
        """Get statistics for all channels."""
        return {
            name: control.get_stats()
            for name, control in self._access_controls.items()
        }


def sanitize_sender_id(sender_id: str) -> str:
    """Sanitize sender ID for logging (mask part of it)."""
    if len(sender_id) <= 8:
        return "***"

    return sender_id[:4] + "***" + sender_id[-4:]


def hash_sender_id(sender_id: str) -> str:
    """Create a hash of sender ID for anonymous tracking."""
    return hashlib.sha256(sender_id.encode()).hexdigest()[:16]
