"""Channel manager for coordinating chat channels."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from loguru import logger

from crabclaw.bus.queue import MessageBus
from crabclaw.channels.base import BaseChannel
from crabclaw.config.schema import Config
from crabclaw.user.manager import UserManager


class ChannelManager:
    """
    Manages chat channels and coordinates message routing.

    Responsibilities:
    - Initialize enabled channels (Telegram, WhatsApp, etc.)
    - Start/stop channels
    - Route outbound messages
    """

    def __init__(self, config: Config, bus: MessageBus):
        self.config = config
        self.bus = bus
        self.channels: dict[str, BaseChannel] = {}
        self.channel_tasks: dict[str, asyncio.Task] = {}
        self._dispatch_task: asyncio.Task | None = None
        self.user_manager = UserManager(config.workspace_path)
        self._route_map: dict[tuple[str, str], str] = {}
        self._instance_routes: dict[str, set[tuple[str, str]]] = {}

        self._init_channels()

    def _init_channels(self) -> None:
        """Initialize channels from user portfolios and (legacy) config file."""
        from crabclaw.channels.registry import discover_all

        groq_key = self.config.providers.groq.api_key
        all_channels = discover_all()

        # 1. Load from per-user portfolio channel configs (active only)
        for user_info in self.user_manager.list_users():
            user_id = user_info.get("user_id")
            if not user_id:
                continue
            channel_sets = self.user_manager.list_channel_configs(user_id)
            for channel_type, records in channel_sets.items():
                if channel_type not in all_channels:
                    logger.warning("Unknown channel type '%s' in portfolio of user '%s'", channel_type, user_id)
                    continue
                cls = all_channels[channel_type]
                for rec in records:
                    if not rec.get("is_active", False):
                        continue
                    key = f"{user_id}:{channel_type}:{rec.get('account_id')}"
                    if key in self.channels:
                        continue
                    try:
                        channel = cls(rec.get("config", {}), self.bus)
                        channel.instance_key = key
                        channel._route_callback = self._register_route
                        channel.transcription_api_key = groq_key
                        self.channels[key] = channel
                        logger.info("Loaded channel instance %s for user %s", key, user_id)
                    except Exception as e:
                        logger.warning("Failed to load channel %s for user %s: %s", channel_type, user_id, e)

        self._validate_allow_from()

    def _register_route(self, channel_type: str, chat_id: str, instance_key: str) -> None:
        route_key = (str(channel_type), str(chat_id))
        self._route_map[route_key] = instance_key
        self._instance_routes.setdefault(instance_key, set()).add(route_key)

    def _forget_routes(self, instance_key: str) -> None:
        routes = self._instance_routes.pop(instance_key, set())
        for route in routes:
            if self._route_map.get(route) == instance_key:
                self._route_map.pop(route, None)

    def _validate_allow_from(self) -> None:
        for name, ch in self.channels.items():
            allow_from = getattr(ch.config, "allow_from", None)
            if allow_from is None or allow_from == []:
                # For dynamic channel settings in user portfolio, gracefully default to public allow.
                logger.warning("%s has empty allow_from; defaulting to ['*']", name)
                if hasattr(ch.config, "allow_from"):
                    ch.config.allow_from = ["*"]
                continue
            if isinstance(allow_from, str):
                try:
                    maybe_list = json.loads(allow_from)
                    if isinstance(maybe_list, list):
                        allow_from = maybe_list
                        ch.config.allow_from = allow_from
                except Exception:
                    pass
            if isinstance(allow_from, list) and "*" in allow_from:
                continue
            # leave strict allow_from as-is (restricted access)

    async def _start_channel(self, key: str, channel: BaseChannel) -> None:
        """Start a single channel instance and capture its task."""
        try:
            logger.info("Starting channel %s", key)
            await channel.start()
        except asyncio.CancelledError:
            logger.warning("Channel %s start task was cancelled", key)
        except Exception as e:
            logger.error("Failed to start channel %s: %s", key, e)

    async def start_channel_instance(self, key: str) -> None:
        """Start a specific channel by internal key."""
        if key not in self.channels:
            logger.warning("Channel key %s not found", key)
            return
        if key in self.channel_tasks and not self.channel_tasks[key].done():
            logger.info("Channel %s already running", key)
            return
        task = asyncio.create_task(self._start_channel(key, self.channels[key]))
        self.channel_tasks[key] = task

    async def stop_channel_instance(self, key: str) -> None:
        """Stop a specific channel instance."""
        channel = self.channels.get(key)
        if not channel:
            logger.warning("Channel key %s not found", key)
            return
        try:
            await channel.stop()
        except Exception as e:
            logger.error("Error stopping channel %s: %s", key, e)
        task = self.channel_tasks.get(key)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            self.channel_tasks.pop(key, None)

    async def reload_channels(self) -> None:
        """Reload channel instances from user portfolios and restart active ones."""
        await self.stop_all()
        self.channels.clear()
        self.channel_tasks.clear()
        self._init_channels()
        await self.start_all()

    async def add_or_update_channel(self, user_id: str, channel_type: str, record: dict[str, Any]) -> None:
        """Add or update a single channel instance for a given user."""
        from crabclaw.channels.registry import discover_all

        if not record.get("is_active", False):
            return

        all_channels = discover_all()
        if channel_type not in all_channels:
            logger.warning("Unknown channel type '%s' for user %s", channel_type, user_id)
            return

        key = f"{user_id}:{channel_type}:{record.get('account_id')}"
        cls = all_channels[channel_type]

        try:
            channel = cls(record.get("config", {}), self.bus)
            channel.instance_key = key
            channel._route_callback = self._register_route
            channel.transcription_api_key = self.config.providers.groq.api_key
            self.channels[key] = channel
            await self.start_channel_instance(key)
            logger.info("Added/updated channel instance %s", key)
        except Exception as e:
            logger.error("Failed to add/update channel %s: %s", key, e)

    async def remove_channel(self, user_id: str, channel_type: str, account_id: str) -> None:
        key = f"{user_id}:{channel_type}:{account_id}"
        if key in self.channel_tasks:
            await self.stop_channel_instance(key)
        if key in self.channels:
            self.channels.pop(key, None)
            self._forget_routes(key)
            logger.info("Removed channel instance %s", key)

    async def set_channel_active(self, user_id: str, channel_type: str, account_id: str, active: bool) -> None:
        key = f"{user_id}:{channel_type}:{account_id}"
        if active:
            # reload from user config for latest values
            recs = self.user_manager.list_channel_configs(user_id).get(channel_type, [])
            rec = next((r for r in recs if r.get("account_id") == account_id), None)
            if rec:
                await self.add_or_update_channel(user_id, channel_type, rec)
            return
        # de-activate existing instance
        if key in self.channels:
            await self.stop_channel_instance(key)
            self._forget_routes(key)
            # keep on-disk config for re-enable later

    async def start_all(self) -> None:
        """Start all channels and the outbound dispatcher."""
        if not self.channels:
            logger.warning("No channels enabled")
            # Keep the task running even when no channels are enabled
            # This prevents the system from shutting down prematurely
            while True:
                await asyncio.sleep(1)
            return

        # Start outbound dispatcher
        self._dispatch_task = asyncio.create_task(self._dispatch_outbound())

        # Start channels
        tasks = []
        for name, channel in self.channels.items():
            logger.info("Starting {} channel...", name)
            tasks.append(asyncio.create_task(self._start_channel(name, channel)))

        # Wait for all to complete (they should run forever)
        await asyncio.gather(*tasks, return_exceptions=True)

    async def stop_all(self) -> None:
        """Stop all channels and the dispatcher."""
        logger.info("Stopping all channels...")

        # Stop dispatcher
        if self._dispatch_task:
            self._dispatch_task.cancel()
            try:
                await self._dispatch_task
            except asyncio.CancelledError:
                pass

        # Stop all channels
        for name, channel in self.channels.items():
            try:
                await channel.stop()
                logger.info("Stopped {} channel", name)
            except Exception as e:
                logger.error("Error stopping {}: {}", name, e)

    async def _dispatch_outbound(self) -> None:
        """Dispatch outbound messages to the appropriate channel."""
        logger.info("Outbound dispatcher started")

        while True:
            try:
                msg = await asyncio.wait_for(
                    self.bus.consume_outbound(),
                    timeout=1.0
                )

                if msg.metadata.get("_progress"):
                    if msg.metadata.get("_tool_hint") and not self.config.messaging.send_tool_hints:
                        continue
                    if not msg.metadata.get("_tool_hint") and not self.config.messaging.send_progress:
                        continue

                # For fanout messages, use normal routing logic since each OutboundMessage
                # already has a specific target channel and chat_id. The fanout flag is set
                # by IOProcessor to indicate this is part of a multi-channel subscription,
                # but routing should still be based on message's channel and chat_id.

                # Normal single-channel dispatch (works for both fanout and non-fanout)
                channel = None
                instance_key = msg.metadata.get("instance_key") or msg.metadata.get("channel_instance")
                if instance_key and instance_key in self.channels:
                    channel = self.channels.get(instance_key)
                else:
                    routed_key = self._route_map.get((str(msg.channel), str(msg.chat_id)))
                    if routed_key:
                        channel = self.channels.get(routed_key)
                    if channel is None:
                        candidates = [k for k, ch in self.channels.items() if getattr(ch, "name", "") == msg.channel]
                        if len(candidates) == 1:
                            channel = self.channels.get(candidates[0])

                logger.info(
                    "ChannelManager: dispatching message to channel={}, chat_id={}, content={}",
                    msg.channel, msg.chat_id, msg.content[:50] if msg.content else ""
                )
                if channel:
                    try:
                        await channel.send(msg)
                        logger.info("ChannelManager: message sent successfully to {}", msg.channel)
                    except Exception as e:
                        logger.error("Error sending to {}: {}", msg.channel, e)
                else:
                    logger.warning("Unknown channel or no route for: {}", msg.channel)

            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

    def get_channel(self, name: str) -> BaseChannel | None:
        """Get a channel by name."""
        return self.channels.get(name)

    def get_status(self) -> dict[str, Any]:
        """Get status of all channels."""
        return {
            name: {
                "enabled": True,
                "running": channel.is_running
            }
            for name, channel in self.channels.items()
        }

    @property
    def enabled_channels(self) -> list[str]:
        """Get list of enabled channel names."""
        return list(self.channels.keys())
