"""Async message queue for decoupled channel-agent communication."""

import asyncio
from loguru import logger

from crabclaw.bus.events import InboundMessage, OutboundMessage


class MessageBus:
    """
    Async message bus that decouples chat channels from the agent core.

    Channels push messages to the inbound queue, and the agent processes
    them and pushes responses to the outbound queue.
    """

    def __init__(self):
        self.inbound: asyncio.Queue[InboundMessage] = asyncio.Queue()
        self.outbound: asyncio.Queue[OutboundMessage] = asyncio.Queue()
        self._subscribers: dict[str, list] = {}
        # For request-response pattern
        self._response_waiters: dict[str, asyncio.Queue] = {}

    def subscribe(self, event_type: str, callback) -> None:
        """Subscribe to a specific event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)
        logger.debug("MessageBus: subscribed to '{}', total subscribers: {}", event_type, len(self._subscribers[event_type]))

    def unsubscribe(self, event_type: str, callback) -> None:
        """Unsubscribe from a specific event type."""
        if event_type in self._subscribers:
            if callback in self._subscribers[event_type]:
                self._subscribers[event_type].remove(callback)

    async def publish(self, event_type: str, data: any) -> None:
        """Publish an event to all subscribers."""
        subscribers = self._subscribers.get(event_type, [])
        logger.debug("MessageBus: publishing '{}', subscribers: {}", event_type, len(subscribers))
        
        # Run callbacks in background to avoid blocking
        for callback in subscribers:
            try:
                if asyncio.iscoroutinefunction(callback):
                    # Run async callback in background
                    asyncio.create_task(callback(data))
                else:
                    # Run sync callback normally
                    callback(data)
            except Exception as e:
                logger.error("MessageBus: error in subscriber callback for '{}': {}", event_type, e)

    async def publish_inbound(self, msg: InboundMessage) -> None:
        """Publish a message from a channel to the agent."""
        logger.debug("MessageBus: publish_inbound from channel={}, sender={}", msg.channel, msg.sender_id)
        await self.inbound.put(msg)
        # Also broadcast to subscribers for real-time updates (e.g., dashboard)
        await self.publish("inbound", msg)

    async def consume_inbound(self) -> InboundMessage:
        """Consume the next inbound message (blocks until available)."""
        return await self.inbound.get()

    async def publish_outbound(self, msg: OutboundMessage) -> None:
        """Publish a response from the agent to channels."""
        logger.debug("MessageBus: publish_outbound to channel={}, chat_id={}", msg.channel, msg.chat_id)
        await self.outbound.put(msg)
        # Also broadcast to subscribers for real-time updates (e.g., dashboard)
        await self.publish("outbound", msg)
        
        # Also notify any waiting response handlers
        session_key = f"{msg.channel}:{msg.chat_id}"
        if session_key in self._response_waiters:
            await self._response_waiters[session_key].put(msg)

    async def consume_outbound(self) -> OutboundMessage:
        """Consume the next outbound message (blocks until available)."""
        return await self.outbound.get()

    def create_response_waiter(self, channel: str, chat_id: str) -> asyncio.Queue:
        """Create a queue to wait for a response to a specific channel/chat."""
        session_key = f"{channel}:{chat_id}"
        if session_key not in self._response_waiters:
            self._response_waiters[session_key] = asyncio.Queue()
        return self._response_waiters[session_key]

    def remove_response_waiter(self, channel: str, chat_id: str) -> None:
        """Remove a response waiter."""
        session_key = f"{channel}:{chat_id}"
        if session_key in self._response_waiters:
            del self._response_waiters[session_key]

    @property
    def inbound_size(self) -> int:
        """Number of pending inbound messages."""
        return self.inbound.qsize()

    @property
    def outbound_size(self) -> int:
        """Number of pending outbound messages."""
        return self.outbound.qsize()
