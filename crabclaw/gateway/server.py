"""Gateway server for receiving external messages."""

from __future__ import annotations

import asyncio
import contextlib
import json
import socket
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from loguru import logger

from crabclaw.bus.broadcaster import BroadcastManager
from crabclaw.bus.events import InboundMessage
from crabclaw.bus.queue import MessageBus
from crabclaw.i18n import translate
from crabclaw.user.manager import UserManager


@dataclass
class GatewayServerConfig:
    enabled: bool = True
    host: str = "127.0.0.1"
    port: int = 18790


class GatewayServer:
    """
    HTTP gateway that accepts external messages and forwards them to the bus.

    Responsibilities:
    - Receive messages from external sources (CLI, webhooks, etc.)
    - Forward to MessageBus for agent processing
    - Wait for and return agent responses
    """

    def __init__(
        self,
        config: Any,
        bus: MessageBus,
        broadcast_manager: BroadcastManager | None = None,
        workspace: Path | None = None,
    ):
        self.bus = bus
        self.broadcast_manager = broadcast_manager
        self.config = config
        self.workspace = workspace or Path.cwd()
        self.user_manager = UserManager(self.workspace)
        self._httpd: ThreadingHTTPServer | None = None
        self._http_thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._chat_history: list[dict] = []
        self._max_history = 100

    @property
    def http_url(self) -> str:
        return f"http://{self.config.host}:{self.config.port}"

    def _session_key_for(self, channel: str, chat_id: str) -> str:
        """Generate a session key for a channel/chat combination."""
        return f"{channel}:{chat_id}"

    def _resolve_user_scope(self, payload: dict[str, Any]) -> str | None:
        explicit_user = str(payload.get("user_id", "")).strip()
        if explicit_user:
            return explicit_user
        channel = str(payload.get("channel", "cli"))
        sender_id = str(payload.get("sender_id", ""))
        chat_id = str(payload.get("chat_id", ""))
        resolved = self.user_manager.resolve_user_by_identity(channel, sender_id)
        if resolved:
            return resolved
        return self.user_manager.resolve_user_by_identity(channel, chat_id)

    def _append_chat_history(self, channel: str, chat_id: str, user_msg: str, agent_msg: str) -> None:
        """Append a chat exchange to history."""
        self._chat_history.append({
            "timestamp": time.time(),
            "channel": channel,
            "chat_id": chat_id,
            "user": user_msg,
            "agent": agent_msg,
        })
        # Trim history if too long
        if len(self._chat_history) > self._max_history:
            self._chat_history = self._chat_history[-self._max_history:]

    def _start_http_in_thread(self) -> None:
        """Start the HTTP server in a background thread."""
        parent = self

        class _Handler(BaseHTTPRequestHandler):
            """HTTP request handler for gateway endpoints."""

            def log_message(self, format: str, *args) -> None:  # noqa: ANN002
                # Suppress default HTTP logging
                pass

            def _send_json(self, status: int, data: dict) -> None:
                """Send a JSON response."""
                body = json.dumps(data, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _handle_message(self, payload: dict[str, Any]) -> None:
                """Handle incoming message from chat CLI."""
                content = payload.get("content", "")
                sender_id = payload.get("sender_id", "cli_user")
                chat_id = payload.get("chat_id", "direct")
                channel = payload.get("channel", "cli")
                request_id = payload.get("request_id") or f"gw-{int(time.time() * 1000)}"
                user_scope = parent._resolve_user_scope(payload)
                metadata = payload.get("metadata", {}) or {}
                if user_scope:
                    metadata["user_id"] = user_scope
                metadata["request_id"] = request_id

                if not parent.bus:
                    self._send_json(500, {"ok": False, "error": "Gateway not connected to message bus"})
                    return

                inbound = InboundMessage(
                    channel=channel,
                    sender_id=sender_id,
                    chat_id=chat_id,
                    content=content,
                    metadata=metadata,
                    session_key_override=(
                        f"user:{user_scope}:{channel}:{chat_id}"
                        if user_scope
                        else parent._session_key_for(channel, chat_id)
                    ),
                )

                result_holder = {"response": None, "event": threading.Event()}

                async def publish_and_respond():
                    response_queue = None
                    if parent.broadcast_manager and user_scope:
                        response_queue = await parent.broadcast_manager.subscribe(scope=user_scope)
                    await parent.bus.publish_inbound(inbound)
                    try:
                        deadline = time.monotonic() + 25.0
                        while True:
                            remaining = deadline - time.monotonic()
                            if remaining <= 0:
                                raise asyncio.TimeoutError()

                            if response_queue is not None:
                                event = await asyncio.wait_for(response_queue.get(), timeout=remaining)
                                if event.get("type") not in {"agent_reply", "outbound_message"}:
                                    continue
                                event_req_id = (
                                    event.get("request_id")
                                    or ((event.get("metadata") or {}).get("request_id"))
                                )
                                if event_req_id and event_req_id != request_id:
                                    continue
                                result_holder["response"] = {
                                    "ok": True,
                                    "content": event.get("content", ""),
                                    "chat_id": event.get("chat_id", chat_id),
                                    "channel": event.get("channel", channel),
                                }
                                break

                            legacy_queue = parent.bus.create_response_waiter(channel, chat_id)
                            outbound = await asyncio.wait_for(legacy_queue.get(), timeout=remaining)
                            result_holder["response"] = {
                                "ok": True,
                                "content": outbound.content,
                                "chat_id": outbound.chat_id,
                                "channel": outbound.channel,
                            }
                            break
                    except asyncio.TimeoutError:
                        result_holder["response"] = {"ok": False, "error": translate("cli.chat.still_thinking_retry")}
                    finally:
                        if response_queue is not None and parent.broadcast_manager and user_scope:
                            await parent.broadcast_manager.unsubscribe(response_queue, scope=user_scope)
                        parent.bus.remove_response_waiter(channel, chat_id)
                        result_holder["event"].set()

                if parent._loop and parent._loop.is_running():
                    asyncio.run_coroutine_threadsafe(publish_and_respond(), parent._loop)
                    result_holder["event"].wait(timeout=180.0)
                    if result_holder["response"]:
                        response = result_holder["response"]
                        if response["ok"]:
                            parent._append_chat_history(channel, chat_id, content, response.get("content", ""))
                            self._send_json(200, response)
                        else:
                            self._send_json(504, response)
                    else:
                        self._send_json(504, {"ok": False, "error": translate("cli.chat.still_thinking_retry")})
                else:
                    self._send_json(500, {"ok": False, "error": "Gateway event loop not running"})

            def do_GET(self) -> None:  # noqa: N802
                if self.path in {"/", "/health", "/healthz"}:
                    return self._send_json(200, {"ok": True, "service": "crabclaw-gateway", "url": parent.http_url})
                return self._send_json(404, {"ok": False, "error": "not_found"})

            def do_POST(self) -> None:  # noqa: N802
                if self.path == "/message":
                    content_length = int(self.headers.get("Content-Length", 0))
                    if content_length == 0:
                        return self._send_json(400, {"ok": False, "error": "Empty request body"})
                    body = self.rfile.read(content_length)
                    try:
                        payload = json.loads(body.decode("utf-8"))
                        self._handle_message(payload)
                    except json.JSONDecodeError:
                        self._send_json(400, {"ok": False, "error": "Invalid JSON"})
                else:
                    self._send_json(404, {"ok": False, "error": "not_found"})

        def _serve() -> None:
            try:
                self._httpd = ThreadingHTTPServer((self.config.host, self.config.port), _Handler)
                logger.info("Gateway HTTP serving {}", self.http_url)
                self._httpd.serve_forever(poll_interval=0.5)
            except Exception as e:
                logger.error("Gateway HTTP server failed: {}", e)

        self._http_thread = threading.Thread(target=_serve, name="gateway-http", daemon=True)
        self._http_thread.start()

    async def start(self) -> None:
        if not self.config.enabled:
            logger.info("Gateway server disabled")
            return

        with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind((self.config.host, self.config.port))
            except OSError as e:
                raise OSError(f"Gateway port {self.config.port} is not available: {e}") from e

        self._loop = asyncio.get_running_loop()
        self._start_http_in_thread()

    async def stop(self) -> None:
        if self._httpd:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
        if self._http_thread:
            self._http_thread.join(timeout=5.0)
            self._http_thread = None
