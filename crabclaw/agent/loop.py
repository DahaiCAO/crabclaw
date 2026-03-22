"""
Agent I/O Processor (Formerly AgentLoop)

This module has been refactored as part of the HAOS integration.
Its role is no longer to be the agent's brain, but to act as a high-speed
I/O processor, or a "spinal cord".

It listens for external messages from the bus and translates them into
Stimulus objects for the Sapiens mind. It also receives Action objects
from the mind and sends them to the appropriate channels for execution.
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import time
import uuid
from typing import TYPE_CHECKING, Any

from loguru import logger

from crabclaw.bus.events import InboundMessage, OutboundMessage
from crabclaw.user.manager import UserManager

# Optional ClawLink support for social interactions
try:
    from clawlink.protocol.envelope import MessageEnvelope
    from clawlink.transport import HTTPTransport
    CLAWLINK_AVAILABLE = True
except ImportError:
    CLAWLINK_AVAILABLE = False
    MessageEnvelope = Any  # Type alias for when clawlink is not installed
    HTTPTransport = Any

if TYPE_CHECKING:
    from crabclaw.bus.broadcaster import BroadcastManager
    from crabclaw.bus.queue import MessageBus
    from crabclaw.sapiens.agent import AgentSapiens
    from crabclaw.sapiens.datatypes import Action

class IOProcessor:
    """
    The I/O Processor for the Sapiens mind.
    """
    def __init__(self, bus: "MessageBus", sapiens_core: "AgentSapiens", broadcast_manager: "BroadcastManager"):
        self.bus = bus
        self.sapiens_core = sapiens_core
        self.broadcast_manager = broadcast_manager
        self._running = False

        # Check if ClawSociety connection is enabled (Social mode)
        try:
            from crabclaw.config.loader import load_config
            config = load_config()
            self._clawlink_enabled = getattr(config, "clawsociety_enabled", False)
            self._discovery_url = getattr(config, "clawsocial_url", "http://127.0.0.1:8000")
        except Exception:
            self._clawlink_enabled = False
            self._discovery_url = "http://127.0.0.1:8000"
            self._workspace = None
        else:
            self._workspace = getattr(config, "workspace_path", None)

        # Hard override if library is missing
        if not CLAWLINK_AVAILABLE:
            self._clawlink_enabled = False

        # Allow env var override for backward compatibility
        env_enabled = os.getenv("SAPIENS_CLAWLINK_ENABLED")
        if env_enabled is not None:
            self._clawlink_enabled = env_enabled not in {"0", "false", "False"}

        self._clawlink_transport: HTTPTransport | None = None
        self._user_manager: UserManager | None = None
        if self._workspace:
            try:
                self._user_manager = UserManager(self._workspace)
            except Exception:
                self._user_manager = None
        self._recent_outbound: dict[str, float] = {}
        self._recent_broadcast_ids: dict[str, float] = {}
        self._scope_origin: dict[str, tuple[str, str, str, float]] = {}
        self._my_did = getattr(
            getattr(self.sapiens_core, "sociology", None),
            "did",
            f"did:claw:agent:{self.sapiens_core.id}",
        )
        self._clawlink_host = os.getenv("CLAWLINK_AGENT_HOST", "127.0.0.1")
        self._clawlink_port = self._derive_listen_port()
        if os.getenv("CLAWLINK_DISCOVERY_URL") or os.getenv("CLAWSOCIETY_URL"):
            self._discovery_url = os.getenv("CLAWLINK_DISCOVERY_URL", os.getenv("CLAWSOCIETY_URL", self._discovery_url))

        # Ensure the outbound action queue is properly initialized for async operations
        self.sapiens_core.outbound_action_queue = asyncio.Queue()

    async def run(self):
        """
        Runs the I/O loop, constantly bridging the external world and the Sapiens mind.
        """
        self._running = True
        logger.info("I/O Processor started. Globally subscribing to BroadcastManager.")

        # Globally subscribe to receive messages from all scopes.
        broadcast_queue = await self.broadcast_manager.subscribe_global()

        await self._start_clawlink_listener()

        # Create three concurrent tasks:
        # 1. Listen for broadcast messages (like user chats)
        # 2. Listen for actions from the Sapiens mind to execute
        # 3. (Still listen to the old bus for backward compatibility or specific commands)
        broadcast_listener_task = asyncio.create_task(self._listen_for_broadcasts(broadcast_queue))
        outbound_task = asyncio.create_task(self._listen_for_outbound_actions())
        inbound_task = asyncio.create_task(self._listen_for_inbound()) # Keep this for now

        try:
            await asyncio.gather(broadcast_listener_task, outbound_task, inbound_task)
        finally:
            await self.broadcast_manager.unsubscribe_global(broadcast_queue)

    async def stop(self):
        """
        Stops the I/O loop.
        """
        self._running = False
        if self._clawlink_transport:
            # Check if stop method exists, otherwise ignore
            if hasattr(self._clawlink_transport, "stop"):
                await self._clawlink_transport.stop()
        logger.info("I/O Processor stopped.")

    def _derive_listen_port(self) -> int:
        base = int(os.getenv("CLAWLINK_AGENT_PORT_BASE", "19000"))
        offset = sum(ord(ch) for ch in str(self.sapiens_core.id)) % 1000
        return base + offset

    async def _start_clawlink_listener(self):
        if not self._clawlink_enabled:
            return
        try:
            self._clawlink_transport = HTTPTransport(
                my_did=self._my_did,
                host=self._clawlink_host,
                port=self._clawlink_port,
                discovery_url=self._discovery_url,
            )
            await self._clawlink_transport.start_listening(self._handle_clawlink_envelope)
            logger.info(
                f"[IO] ClawLink listener ready for {self._my_did} on {self._clawlink_host}:{self._clawlink_port}"
            )
        except Exception:
            self._clawlink_transport = None
            logger.exception("[IO] Failed to start ClawLink listener.")

    async def _handle_clawlink_envelope(self, envelope: MessageEnvelope):
        self.sapiens_core.route_protocol_envelope(envelope)
        payload = envelope.content or {}
        message = str(payload.get("message", payload))
        inbound_msg = InboundMessage(
            channel="agent",
            sender_id=envelope.from_agent,
            chat_id=f"agent:{envelope.from_agent}",
            content=message,
            metadata={
                "intent": envelope.intent,
                "trace_id": envelope.trace_id,
                "message_id": envelope.id,
            },
        )
        await self.bus.publish_inbound(inbound_msg)

    async def _listen_for_broadcasts(self, queue: asyncio.Queue):
        """Listens for broadcast messages and converts them to Stimuli."""
        from crabclaw.sapiens.datatypes import Stimulus

        while self._running:
            try:
                msg = await queue.get()
                logger.debug(f"[IO] Received broadcast message: {msg}")

                if msg.get("type") == "user_message":
                    scope = str(msg.get("scope", ""))
                    event_id = str(msg.get("event_id", "")).strip()
                    if event_id and self._is_duplicate_broadcast(event_id):
                        continue
                    source_channel = str(msg.get("source_channel", ""))
                    source_chat = str(msg.get("chat_id", ""))
                    sender_id = str(msg.get("sender_id", ""))
                    if scope and source_channel and source_chat:
                        self._scope_origin[scope] = (source_channel, source_chat, sender_id, time.time())
                    # Convert the broadcast message into a mental Stimulus
                    stimulus = Stimulus(
                        source=f"{msg.get('source_channel', 'unknown')}:{msg.get('chat_id', 'unknown')}",
                        type="message",
                        content=msg.get("content", ""),
                        intensity=0.8, # Natural intensity for a direct message
                        urgency=0.7,   # Slightly higher urgency as it's a real-time chat
                        timestamp=msg.get("timestamp", 0),
                        metadata=msg
                    )
                    self.sapiens_core.psychology.workspace.add_stimulus(stimulus)

            except Exception:
                logger.exception("Error in I/O broadcast listener.")

    async def _listen_for_inbound(self):
        """Listens for messages from the outside world and converts them to Stimuli."""
        from crabclaw.sapiens.datatypes import Stimulus

        while self._running:
            try:
                msg: InboundMessage = await asyncio.wait_for(self.bus.consume_inbound(), timeout=1.0)
                logger.debug(f"[IO] Received InboundMessage from bus: {msg.content[:50]}")
                if self._is_inbound_echo(msg):
                    continue

                scope = self._resolve_scope_from_inbound(msg)
                if scope:
                    self._scope_origin[scope] = (msg.channel, msg.chat_id, msg.sender_id, time.time())

                # Convert the external message into a mental Stimulus
                # Natural intensity and urgency for a standard stimulus
                stimulus = Stimulus(
                    source=f"{msg.channel}:{msg.chat_id}",
                    type="message",
                    content=msg.content,
                    intensity=0.8,
                    urgency=0.5,
                    timestamp=msg.timestamp.timestamp(),
                )

                # Send the stimulus to the mind's perception system
                # In a more advanced version, this would go to a PerceptionSystem component.
                self.sapiens_core.psychology.workspace.add_stimulus(stimulus)

            except asyncio.TimeoutError:
                continue
            except Exception:
                logger.exception("Error in I/O inbound listener.")

    async def _listen_for_outbound_actions(self):
        """Listens for Action objects decided by the Sapiens mind and executes them."""
        while self._running:
            try:
                # This requires a new queue in the Sapiens core to push actions to.
                action: Action = await self.sapiens_core.get_outbound_action()
                logger.info(f"[IO] Received Action from Sapiens mind: {action.name}, recipient: {action.params.get('recipient', 'N/A')}")

                # For now, we only handle 'send_message' actions.
                if action.name == "send_message":
                    content = action.params.get("content", "")
                    recipient = str(action.params.get("recipient", ""))
                    reply_scope = (
                        action.params.get("scope")
                        or action.params.get("user_id")
                        or action.params.get("scope_user_id")
                        or recipient  # Use recipient as scope if it's a user ID
                    )
                    request_id = (
                        action.params.get("request_id")
                        or ((action.params.get("metadata") or {}).get("request_id"))
                        or ""
                    )
                    source_channel = action.params.get("source_channel") or ""
                    source_chat_id = action.params.get("source_chat_id") or ""

                    if not content:
                        continue

                    if reply_scope:
                        await self.broadcast_manager.publish(
                            scope=reply_scope,
                            message={
                                "type": "agent_reply",
                                "content": content,
                                "timestamp": time.time(),
                                "request_id": request_id,
                            },
                        )
                        logger.info(f"[IO] Published agent_reply to scope {reply_scope}, content_length={len(content)}")

                    outbound_targets = self._collect_outbound_targets(
                        reply_scope=reply_scope,
                        recipient=recipient,
                        source_channel=source_channel,
                        source_chat_id=source_chat_id,
                    )

                    sent = 0
                    for target_channel, target_chat_id in outbound_targets:
                        # Avoid rebroadcasting to dashboard via outbound paths when already sent as agent_reply.
                        # This prevents duplicate frontend messages and 1001 caused by redundant websocket traffic.
                        if target_channel == "dashboard" and target_chat_id == "direct":
                            logger.info(f"[IO] Skipping outbound publish to dashboard/direct (already agent_reply) for scope={reply_scope}")
                            continue

                        event_id = self._make_event_id(
                            "out",
                            {
                                "scope": reply_scope or "",
                                "channel": target_channel,
                                "chat_id": target_chat_id,
                                "content": content,
                                "request_id": request_id,
                            },
                        )
                        self._remember_outbound(target_channel, target_chat_id, content)
                        outbound = OutboundMessage(
                            channel=target_channel,
                            chat_id=target_chat_id,
                            content=content,
                            metadata={
                                "scope": reply_scope or "",
                                "request_id": request_id,
                                "fanout": True,
                                "source": "sapiens",
                                "event_id": event_id,
                            },
                        )
                        await self.bus.publish_outbound(outbound)
                        sent += 1

                    if sent == 0 and not reply_scope:
                        logger.error(f"[IO] Cannot route outbound message, missing scope and recipient route. Action: {action}")
                else:
                    # In the full architecture, this would delegate to the ActionExecutor
                    logger.warning(f"[IO] Don't know how to execute action: {action.name}")

            except asyncio.TimeoutError:
                continue
            except Exception:
                logger.exception("Error in I/O outbound listener.")

    def _collect_outbound_targets(
        self,
        reply_scope: str | None,
        recipient: str,
        source_channel: str,
        source_chat_id: str,
    ) -> list[tuple[str, str]]:
        outbound_targets: list[tuple[str, str]] = []
        if reply_scope and self._user_manager:
            mappings = self._user_manager.list_identity_mappings(reply_scope)
            origin = self._scope_origin.get(reply_scope)
            for mapping in mappings:
                ch = str(mapping.get("channel", "")).strip()
                external_id = str(mapping.get("external_id", "")).strip()
                if ch and external_id:
                    if origin and ch == origin[0] and external_id == origin[1]:
                        continue
                    outbound_targets.append((ch, external_id))
            if not outbound_targets and origin and origin[0] != 'dashboard':
                outbound_targets.append((origin[0], origin[1]))
            return outbound_targets
        if ":" in recipient and not recipient.startswith("did:"):
            ch, target_chat = recipient.split(":", 1)
            if ch and target_chat:
                return [(ch, target_chat)]
        if source_channel and source_chat_id:
            return [(source_channel, source_chat_id)]
        return outbound_targets

    @staticmethod
    def _make_event_id(prefix: str, payload: dict) -> str:
        raw = str(sorted(payload.items()))
        digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
        return f"{prefix}-{digest}"

    def _remember_outbound(self, channel: str, chat_id: str, content: str) -> None:
        key = self._fingerprint(channel, chat_id, content)
        now = time.time()
        self._recent_outbound[key] = now
        self._prune_recent(self._recent_outbound, ttl_s=20.0)

    def _is_inbound_echo(self, msg: InboundMessage) -> bool:
        key = self._fingerprint(msg.channel, msg.chat_id, msg.content)
        now = time.time()
        ts = self._recent_outbound.get(key)
        if ts is None:
            return False
        if now - ts > 20.0:
            self._recent_outbound.pop(key, None)
            return False
        return True

    @staticmethod
    def _fingerprint(channel: str, chat_id: str, content: str) -> str:
        text = f"{channel}|{chat_id}|{content.strip()}"
        return hashlib.sha1(text.encode("utf-8")).hexdigest()

    def _is_duplicate_broadcast(self, event_id: str) -> bool:
        now = time.time()
        ts = self._recent_broadcast_ids.get(event_id)
        self._prune_recent(self._recent_broadcast_ids, ttl_s=120.0)
        if ts and now - ts <= 120.0:
            return True
        self._recent_broadcast_ids[event_id] = now
        return False

    @staticmethod
    def _prune_recent(cache: dict[str, float], ttl_s: float) -> None:
        now = time.time()
        stale = [k for k, t in cache.items() if now - t > ttl_s]
        for key in stale:
            cache.pop(key, None)

    def _resolve_scope_from_inbound(self, msg: InboundMessage) -> str:
        metadata = msg.metadata or {}
        scope = str(metadata.get("user_id") or metadata.get("scope_user_id") or "").strip()
        if scope:
            return scope
        if self._user_manager:
            by_sender = self._user_manager.resolve_user_by_identity(msg.channel, msg.sender_id)
            if by_sender:
                return by_sender
            by_chat = self._user_manager.resolve_user_by_identity(msg.channel, msg.chat_id)
            if by_chat:
                return by_chat
        return ""

    async def _send_agent_message(
        self,
        to_did: str,
        content: str,
        intent: str = "task.propose",
        metadata: dict | None = None,
    ) -> bool:
        if not self._clawlink_transport:
            return False
        envelope = MessageEnvelope(
            from_agent=self._my_did,
            to_agent=to_did,
            intent=intent,
            content={
                "message": content,
                "metadata": metadata or {},
            },
            trace_id=str(uuid.uuid4()),
        )
        return await self._clawlink_transport.send(envelope)
