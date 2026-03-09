"""Chat channels module with plugin architecture."""

from crabclaw.channels.base import BaseChannel
from crabclaw.channels.manager import ChannelManager

__all__ = ["BaseChannel", "ChannelManager"]
