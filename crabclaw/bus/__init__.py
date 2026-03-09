"""Message bus module for decoupled channel-agent communication."""

from crabclaw.bus.events import InboundMessage, OutboundMessage
from crabclaw.bus.queue import MessageBus

__all__ = ["MessageBus", "InboundMessage", "OutboundMessage"]
