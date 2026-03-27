#!/usr/bin/env python3
"""
Test script to check channel status and message routing
"""

import asyncio
from pathlib import Path

from crabclaw.config.loader import load_config
from crabclaw.channels.manager import ChannelManager
from crabclaw.bus.queue import MessageBus

async def test_channel_status():
    print("Testing channel status...")
    
    # Load config
    config = load_config()
    print(f"Channel mode: {config.channel_mode}")
    
    # Create message bus and channel manager
    bus = MessageBus()
    channel_manager = ChannelManager(config, bus)
    
    # Print channel status
    print(f"\nEnabled channels: {channel_manager.enabled_channels}")
    
    for channel_key, channel in channel_manager.channels.items():
        print(f"\nChannel: {channel_key}")
        print(f"  Name: {channel.name}")
        print(f"  Display name: {channel.display_name}")
        print(f"  Is running: {channel.is_running}")
        
        # Check if Feishu channel has client initialized
        if channel.name == "feishu":
            print(f"  Client initialized: {getattr(channel, '_client', None) is not None}")
            print(f"  WebSocket client: {getattr(channel, '_ws_client', None) is not None}")
            print(f"  WebSocket thread: {getattr(channel, '_ws_thread', None) is not None}")
            if hasattr(channel, '_ws_thread') and channel._ws_thread:
                print(f"  WebSocket thread alive: {channel._ws_thread.is_alive()}")
    
    # Clean up
    await channel_manager.stop_all()

if __name__ == "__main__":
    asyncio.run(test_channel_status())
