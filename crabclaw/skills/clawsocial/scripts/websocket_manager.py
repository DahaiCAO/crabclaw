#!/usr/bin/env python3
"""
WebSocket Client Manager for Crabclaw

Manages WebSocket connections and integrates with Crabclaw's MessageBus
"""
import asyncio
import logging
from typing import Optional, Callable

from crabclaw.bus.queue import MessageBus
from crabclaw.bus.events import InboundMessage
from .websocket_client import WebSocketClient, Message

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages WebSocket connections and integrates with Crabclaw's MessageBus."""
    
    def __init__(self, agent_id: str, bus: MessageBus):
        """Initialize WebSocket manager.
        
        Args:
            agent_id: The agent ID for this Crabclaw instance
            bus: The MessageBus to integrate with
        """
        self.agent_id = agent_id
        self.bus = bus
        self.client: Optional[WebSocketClient] = None
        self.is_connected = False
    
    async def start(self):
        """Start WebSocket connection and message processing."""
        if self.client:
            await self.stop()
        
        # Create WebSocket client with message handler that integrates with MessageBus
        self.client = WebSocketClient(
            agent_id=self.agent_id,
            on_message=self._handle_message,
            on_connect=self._handle_connect,
            on_disconnect=self._handle_disconnect
        )
        
        # Connect to WebSocket server
        success = await self.client.connect()
        if not success:
            logger.error(f"Failed to connect WebSocket for agent {self.agent_id}")
            return False
        
        self.is_connected = True
        logger.info(f"WebSocket manager started for agent {self.agent_id}")
        return True
    
    async def stop(self):
        """Stop WebSocket connection."""
        if self.client:
            await self.client.disconnect()
            self.client = None
        self.is_connected = False
        logger.info(f"WebSocket manager stopped for agent {self.agent_id}")
    
    async def send_message(self, to_agent: str, content: str, content_type: str = "text"):
        """Send a message via WebSocket.
        
        Args:
            to_agent: The recipient agent ID
            content: The message content
            content_type: The content type (default: "text")
        """
        if not self.client or not self.is_connected:
            logger.error("WebSocket not connected, cannot send message")
            return False
        
        try:
            result = await self.client.send_message(
                to_agent=to_agent,
                content=content,
                content_type=content_type
            )
            logger.debug(f"Message sent result: {result}")
            return True
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False
    
    def _handle_message(self, msg: Message):
        """Handle incoming WebSocket message and publish to MessageBus.
        
        Args:
            msg: The incoming message
        """
        # Create InboundMessage for MessageBus
        inbound_msg = InboundMessage(
            channel="clawsocial",
            sender_id=msg.from_agent,
            chat_id=f"clawsocial:{msg.from_agent}",  # Use sender ID as chat ID with channel prefix
            content=msg.content,
            metadata={
                "msg_id": msg.msg_id,
                "msg_type": msg.msg_type,
                "timestamp": msg.timestamp,
                "content_type": msg.content_type,
                **(msg.metadata or {})
            }
        )
        
        # Publish to MessageBus with error handling
        async def publish_with_error_handling():
            try:
                await self.bus.publish_inbound(inbound_msg)
                logger.info(f"WebSocket message published to MessageBus: {msg.from_agent} -> {msg.content[:50]}...")
            except Exception as e:
                logger.error(f"Failed to publish WebSocket message to MessageBus: {e}")
        
        asyncio.create_task(publish_with_error_handling())
    
    def _handle_connect(self):
        """Handle WebSocket connection established."""
        logger.info(f"WebSocket connected for agent {self.agent_id}")
    
    def _handle_disconnect(self):
        """Handle WebSocket connection closed."""
        logger.info(f"WebSocket disconnected for agent {self.agent_id}")
        self.is_connected = False
