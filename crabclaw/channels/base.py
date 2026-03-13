"""Base channel interface for chat platforms."""

from abc import ABC, abstractmethod
from typing import Any

from loguru import logger

from crabclaw.bus.events import InboundMessage, OutboundMessage
from crabclaw.bus.queue import MessageBus
from crabclaw.channels.security import AccessControl, RateLimitConfig


class BaseChannel(ABC):
    """
    Abstract base class for chat channel implementations.

    Each channel (Telegram, Discord, etc.) should implement this interface
    to integrate with the Crabclaw message bus.
    """

    name: str = "base"

    def __init__(self, config: Any, bus: MessageBus):
        """
        Initialize the channel.

        Args:
            config: Channel-specific configuration.
            bus: The message bus for communication.
        """
        self.config = config
        self.bus = bus
        self._running = False

        # Initialize access control with rate limiting
        allow_from = getattr(config, "allow_from", [])
        rate_limit_config = RateLimitConfig(
            max_requests_per_minute=getattr(config, "rate_limit_per_minute", 60),
            max_requests_per_hour=getattr(config, "rate_limit_per_hour", 1000),
        )
        self._access_control = AccessControl(
            allow_from=allow_from,
            rate_limit_config=rate_limit_config,
        )

    @abstractmethod
    async def start(self) -> None:
        """
        Start the channel and begin listening for messages.

        This should be a long-running async task that:
        1. Connects to the chat platform
        2. Listens for incoming messages
        3. Forwards messages to the bus via _handle_message()
        """
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop the channel and clean up resources."""
        pass

    @abstractmethod
    async def send(self, msg: OutboundMessage) -> None:
        """
        Send a message through this channel.

        Args:
            msg: The message to send.
        """
        pass

    def is_allowed(self, sender_id: str) -> bool:
        """Check if *sender_id* is permitted.  Empty list → deny all; ``"*"`` → allow all."""
        allowed, reason = self._access_control.is_allowed(sender_id)
        if not allowed and reason:
            logger.warning(f"{self.name}: Access denied for {sender_id}: {reason}")
        return allowed

    async def _handle_message(
        self,
        sender_id: str,
        chat_id: str,
        content: str,
        media: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        session_key: str | None = None,
    ) -> None:
        """
        Handle an incoming message from the chat platform.

        This method checks permissions and forwards to the bus.

        Args:
            sender_id: The sender's identifier.
            chat_id: The chat/channel identifier.
            content: Message text content.
            media: Optional list of media URLs.
            metadata: Optional channel-specific metadata.
            session_key: Optional session key override (e.g. thread-scoped sessions).
        """
        # Check access control
        allowed, reason = self._access_control.is_allowed(sender_id)
        if not allowed:
            logger.warning(
                "Access denied for sender {} on channel {}: {}. "
                "Add them to allowFrom list in config to grant access.",
                sender_id, self.name, reason,
            )
            return

        # Check rate limiting
        rate_allowed, rate_reason = await self._access_control.check_rate_limit(sender_id)
        if not rate_allowed:
            logger.warning(
                "Rate limit exceeded for sender {} on channel {}: {}",
                sender_id, self.name, rate_reason,
            )
            return

        msg = InboundMessage(
            channel=self.name,
            sender_id=str(sender_id),
            chat_id=str(chat_id),
            content=content,
            media=media or [],
            metadata=metadata or {},
            session_key_override=session_key,
        )

        await self.bus.publish_inbound(msg)

    @property
    def is_running(self) -> bool:
        """Check if the channel is running."""
        return self._running

    def get_security_stats(self) -> dict[str, Any]:
        """Get security statistics for this channel."""
        return self._access_control.get_stats()

    def reset_rate_limit(self, sender_id: str | None = None) -> None:
        """Reset rate limiter for a specific sender or all senders."""
        self._access_control.rate_limiter.reset(sender_id)
