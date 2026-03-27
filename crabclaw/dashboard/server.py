from __future__ import annotations

import asyncio
import contextlib
import json
import socket
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import jwt
from loguru import logger
from websockets.server import serve

from crabclaw.bus.broadcaster import BroadcastManager
from crabclaw.user.manager import UserManager
from crabclaw.session.manager import SessionManager
from crabclaw.i18n import get_supported_languages


class TokenError(Exception):
    pass

def issue_token(subject: str, keys: dict, expires_delta: timedelta = timedelta(days=7)) -> str:
    """Issue a JWT token."""
    payload = {
        "sub": subject,
        "exp": datetime.utcnow() + expires_delta,
        "iat": datetime.utcnow(),
    }
    # Use the first available key or a default one if none provided
    secret = list(keys.values())[0] if keys else "default-insecure-secret-key"
    return jwt.encode(payload, secret, algorithm="HS256")

def decode_token(token: str, keys: dict) -> dict:
    """Decode and verify a JWT token."""
    try:
        # We try to decode without verifying signature first to get the kid if we used multiple keys
        # But for simplicity, we just try all keys or the default one
        secrets = list(keys.values()) if keys else ["default-insecure-secret-key"]

        last_error = None
        for secret in secrets:
            try:
                return jwt.decode(token, secret, algorithms=["HS256"])
            except jwt.InvalidTokenError as e:
                last_error = e

        raise last_error if last_error else jwt.InvalidTokenError("No valid keys found")
    except Exception as e:
        raise TokenError(str(e))


@dataclass
class DashboardConfig:
    enabled: bool = True
    host: str = "127.0.0.1"
    http_port: int = 18791
    ws_port: int = 18792


class DashboardServer:
    """Static HTTP + WebSocket streaming server."""

    def __init__(
        self,
        broadcast_manager: BroadcastManager,
        *,
        static_dir: Path,
        config: DashboardConfig | None = None,
        workspace: Path | None = None,
        scheduler = None,
    ) -> None:
        self.broadcast_manager = broadcast_manager
        self.static_dir = static_dir
        self.config = config or DashboardConfig()
        self._jwt_keys = self._get_jwt_keys()
        self.workspace = workspace or self._resolve_workspace()
        self.user_manager = UserManager(self.workspace)
        self.session_manager = SessionManager(self.workspace)
        self.scheduler = scheduler

        self._httpd: ThreadingHTTPServer | None = None
        self._http_thread: threading.Thread | None = None
        self._ws_server: Any | None = None
        self._ws_task: asyncio.Task | None = None

    def _resolve_workspace(self) -> Path:
        try:
            from crabclaw.config.loader import load_config
            config = load_config()
            return Path(config.workspace_path).expanduser().resolve()
        except Exception:
            return Path.cwd()

    @property
    def http_url(self) -> str:
        return f"http://{self.config.host}:{self.config.http_port}/"

    @property
    def ws_url(self) -> str:
        return f"ws://{self.config.host}:{self.config.ws_port}/ws"

    def _start_http_in_thread(self) -> None:
        parent = self

        class _Handler(SimpleHTTPRequestHandler):
            def do_POST(self):
                try:
                    content_length = int(self.headers.get('Content-Length', 0))
                    post_data = self.rfile.read(content_length) if content_length > 0 else b""
                    body = json.loads(post_data.decode('utf-8')) if post_data else {}

                    if self.path == '/api/login':
                        parent._handle_login(self, body)
                    elif self.path == '/api/register':
                        parent._handle_register(self, body)
                    elif self.path == '/api/me':
                        parent._handle_me(self)
                    elif self.path == '/api/logout':
                        parent._handle_logout(self)
                    elif self.path == '/api/delete-account':
                        parent._handle_delete_account(self, body)
                    else:
                        self.send_response(404)
                        self.end_headers()
                        self.wfile.write(b'Not Found')
                except Exception as e:
                    logger.error(f"Error handling POST request: {e}")
                    self.send_response(500)
                    self.end_headers()
                    self.wfile.write(b'Internal Server Error')

            def log_message(self, format: str, *args) -> None:  # noqa: A002
                logger.debug("Dashboard HTTP: " + format, *args)

        def _serve() -> None:
            try:
                self._httpd = ThreadingHTTPServer(
                    (self.config.host, self.config.http_port),
                    lambda *a, **kw: _Handler(*a, directory=str(self.static_dir), **kw),
                )
                logger.info("Dashboard HTTP serving %s", self.http_url)
                self._httpd.serve_forever(poll_interval=0.5)
            except Exception as e:
                logger.error("Dashboard HTTP server failed: %s", e)

        self._http_thread = threading.Thread(target=_serve, name="dashboard-http", daemon=True)
        self._http_thread.start()

    def _get_jwt_keys(self) -> dict[str, str]:
        try:
            from crabclaw.config.loader import load_config
            config = load_config()
            # Try to get from nested config
            if hasattr(config, "security") and hasattr(config.security, "jwt_keys"):
                return config.security.jwt_keys
            # Try flat config
            if hasattr(config, "jwt_keys") and isinstance(config.jwt_keys, dict):
                 return config.jwt_keys
            # Default fallback for local dev if not present
            return {"default": "crabclaw-local-dev-secret-key-123"}
        except Exception as e:
            logger.error(f"Could not load JWT keys from config: {e}")
            return {"default": "crabclaw-local-dev-secret-key-123"}

    def _send_json_response(self, handler, status_code, data):
        handler.send_response(status_code)
        handler.send_header('Content-type', 'application/json')
        handler.end_headers()
        handler.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def _handle_login(self, handler, body):
        username = body.get('username')
        password = body.get('password')
        user = self.user_manager.authenticate(username, password)

        if user:
            access_token = issue_token(subject=user.user_id, keys=self._jwt_keys)
            self._send_json_response(handler, 200, {
                "ok": True,
                "access_token": access_token,
                "user": {"user_id": user.user_id, "username": user.username, "display_name": user.display_name, "is_admin": user.is_admin}
            })
        else:
            self._send_json_response(handler, 401, {"ok": False, "error": "Invalid username or password"})

    def _handle_register(self, handler, body):
        username = body.get('username')
        password = body.get('password')
        display_name = body.get('display_name', username)

        if self.user_manager.get_user_by_username(username):
            self._send_json_response(handler, 400, {"ok": False, "error": "Username already exists"})
            return

        user = self.user_manager.create_user(username, display_name, password)

        access_token = issue_token(subject=user.user_id, keys=self._jwt_keys)
        self._send_json_response(handler, 201, {
            "ok": True,
            "access_token": access_token,
            "user": {"user_id": user.user_id, "username": user.username, "display_name": user.display_name, "is_admin": user.is_admin}
        })

    def _handle_me(self, handler):
        token = self._extract_http_token(handler)
        if not token:
            self._send_json_response(handler, 401, {"ok": False, "error": "Missing authentication token"})
            return
        keys = self._get_jwt_keys()
        if not keys:
            self._send_json_response(handler, 500, {"ok": False, "error": "Server authentication is not configured"})
            return
        try:
            claims = decode_token(token, keys)
            user_id = claims.get("sub")
            if not user_id:
                self._send_json_response(handler, 401, {"ok": False, "error": "Invalid token"})
                return
            user = self.user_manager.get_user_by_id(user_id)
            if not user:
                self._send_json_response(handler, 404, {"ok": False, "error": "User not found"})
                return
            self._send_json_response(
                handler,
                200,
                {
                    "ok": True,
                    "user": {
                        "user_id": user.user_id,
                        "username": user.username,
                        "display_name": user.display_name,
                        "is_admin": user.is_admin,
                    },
                },
            )
        except TokenError as e:
            self._send_json_response(handler, 401, {"ok": False, "error": f"Invalid or expired token: {e}"})

    def _extract_http_token(self, handler) -> str:
        auth_header = handler.headers.get("Authorization", "")
        if auth_header.lower().startswith("bearer "):
            return auth_header[7:].strip()
        cookie_header = handler.headers.get("Cookie", "")
        if cookie_header:
            cookie = SimpleCookie()
            cookie.load(cookie_header)
            if "access_token" in cookie:
                return cookie["access_token"].value
        return ""

    def _handle_logout(self, handler):
        self._send_json_response(handler, 200, {"ok": True})

    def _handle_delete_account(self, handler, body):
        token = self._extract_http_token(handler)
        if not token:
            self._send_json_response(handler, 401, {"ok": False, "error": "Missing authentication token"})
            return
        keys = self._get_jwt_keys()
        if not keys:
            self._send_json_response(handler, 500, {"ok": False, "error": "Server authentication is not configured"})
            return
        try:
            claims = decode_token(token, keys)
            user_id = claims.get("sub")
            if not user_id:
                self._send_json_response(handler, 401, {"ok": False, "error": "Invalid token"})
                return
            user = self.user_manager.get_user_by_id(user_id)
            if not user:
                self._send_json_response(handler, 404, {"ok": False, "error": "User not found"})
                return
            if user.is_admin:
                self._send_json_response(handler, 403, {"ok": False, "error": "Admin account cannot be deleted"})
                return
            if not self.user_manager.delete_user(user_id):
                self._send_json_response(handler, 500, {"ok": False, "error": "Delete failed"})
                return
            self._send_json_response(handler, 200, {"ok": True})
        except TokenError as e:
            self._send_json_response(handler, 401, {"ok": False, "error": f"Invalid or expired token: {e}"})

    async def _authenticate_ws_user(self, ws) -> str:
        """Authenticates a WebSocket user and returns their user ID (subject)."""
        # 1. Try to get token from Authorization header
        auth_header = ws.request_headers.get('Authorization')
        token = None
        if auth_header and auth_header.lower().startswith('bearer '):
            token = auth_header[7:]

        # 2. If not in header, try query parameter
        if not token:
            # The websockets library doesn't directly expose query params in the handler,
            # so we need to parse the path.
            from urllib.parse import parse_qs, urlparse
            parsed_path = urlparse(ws.path)
            query_params = parse_qs(parsed_path.query)
            if 'token' in query_params:
                token = query_params['token'][0]

        if not token:
            raise ConnectionRefusedError("No authentication token provided.")

        # 3. Decode the token
        keys = self._get_jwt_keys()
        if not keys:
            raise ConnectionRefusedError("Server authentication is not configured.")

        try:
            claims = decode_token(token, keys)
            user_id = claims.get("sub")
            if not user_id:
                raise TokenError("Token is missing 'sub' (subject) claim.")
            return user_id
        except TokenError as e:
            raise ConnectionRefusedError(f"Invalid or expired token: {e}")

    async def _ws_loop(self) -> None:
        async def _handler(ws, path: str | None = None) -> None:
            user_id = None
            q = None
            try:
                user_id = await self._authenticate_ws_user(ws)
                q_user = await self.broadcast_manager.subscribe(scope=user_id)
                q_system = await self.broadcast_manager.subscribe(scope="system:state")
                logger.info(f"WebSocket client connected for user '{user_id}'")

                await ws.send(json.dumps({"type": "hello", "data": {"ws": self.ws_url, "user_id": user_id}}, ensure_ascii=False))
                await ws.send(json.dumps({"type": "chat_history", "data": {"messages": self._get_chat_history(user_id)}}, ensure_ascii=False))
                await ws.send(json.dumps(self._safe_get_channels_payload(user_id), ensure_ascii=False))
                # Send initial internal state if scheduler is available
                if self.scheduler and hasattr(self.scheduler, 'state'):
                    await ws.send(json.dumps({"type": "internal_state", "data": self.scheduler.state.model_dump()}, ensure_ascii=False))

                async def broadcast_loop():
                    while True:
                        try:
                            task_user = asyncio.create_task(q_user.get())
                            task_system = asyncio.create_task(q_system.get())
                            done, pending = await asyncio.wait(
                                [task_user, task_system],
                                return_when=asyncio.FIRST_COMPLETED,
                            )

                            msg = None
                            for task in done:
                                msg = task.result()
                                break

                            # Cancel pending tasks to avoid resource leaks
                            for task in pending:
                                task.cancel()
                                try:
                                    await task
                                except asyncio.CancelledError:
                                    pass

                            if msg is None:
                                continue

                            msg_type = msg.get('type', 'unknown')
                            if msg_type == 'unknown' and 'agent_id' in msg:
                                # Legacy weekly format where internal state was sent as raw object
                                msg = {"type": "internal_state", "data": msg}
                                msg_type = "internal_state"

                            if ws.closed:
                                logger.warning(f"Broadcast loop: WS already closed for user '{user_id}', stopping loop")
                                break

                            logger.debug(f"Broadcast loop: Sending message to user '{user_id}': {msg_type}")
                            if msg_type == "user_message":
                                # Skip sending user_message back to the client as it's already displayed
                                continue

                            # Handle inbound messages from other channels (show in dashboard)
                            if msg_type == "inbound_message":
                                try:
                                    session = self.session_manager.get_or_create("dashboard", user_scope=user_id)
                                    session.add_message("user", msg.get("content", ""))
                                    self.session_manager.save(session)
                                except Exception as e:
                                    logger.warning(f"Failed to persist inbound history: {e}")

                            # Persist assistant messages for history
                            if msg_type in ("agent_reply", "outbound_message"):
                                try:
                                    session = self.session_manager.get_or_create("dashboard", user_scope=user_id)
                                    session.add_message("assistant", msg.get("content", ""))
                                    self.session_manager.save(session)
                                except Exception as e:
                                    logger.warning(f"Failed to persist assistant history: {e}")

                            await ws.send(json.dumps(msg, ensure_ascii=False))
                            logger.debug(f"Broadcast loop: Message sent successfully")
                        except Exception as e:
                            logger.error(f"Broadcast loop error for user '{user_id}': {e}", exc_info=True)
                            # Keep the stream alive for transient/bad-payload events.
                            # A single bad event should not stop portrait/state updates.
                            await asyncio.sleep(0.2)
                            continue

                async def handle_messages():
                    async for msg in ws:
                        try:
                            data = json.loads(msg)
                            msg_type = data.get("type")

                            if msg_type == "chat_message":
                                chat_data = data.get("data", {})
                                message_content = chat_data.get("message", "")
                                if message_content:
                                    logger.debug(f"Received chat_message from user '{user_id}': {message_content[:50]}...")

                                    # Persist user message in history
                                    try:
                                        session = self.session_manager.get_or_create("dashboard", user_scope=user_id)
                                        session.add_message("user", message_content)
                                        self.session_manager.save(session)
                                    except Exception as e:
                                        logger.warning(f"Failed to persist user history: {e}")

                                    broadcast_message = {
                                        "type": "user_message",
                                        "source_channel": "dashboard",
                                        "chat_id": "direct",
                                        "sender_id": user_id, # Authenticated user ID
                                        "content": message_content,
                                        "timestamp": time.time()
                                    }
                                    await self.broadcast_manager.publish(scope=user_id, message=broadcast_message)
                                    logger.debug(f"Published user_message to broadcast manager")
                            elif msg_type == "get_channels":
                                await ws.send(json.dumps(self._safe_get_channels_payload(user_id), ensure_ascii=False))
                            elif msg_type == "get_providers":
                                await ws.send(
                                    json.dumps(
                                        {"type": "providers", "data": {"providers": self._get_providers()}},
                                        ensure_ascii=False,
                                    )
                                )
                            elif msg_type == "get_config":
                                await ws.send(
                                    json.dumps(
                                        {"type": "config", "data": self._get_config()},
                                        ensure_ascii=False,
                                    )
                                )
                            elif msg_type == "get_skills":
                                skills = self._get_skills()
                                await ws.send(
                                    json.dumps(
                                        {"type": "skills", "data": skills},
                                        ensure_ascii=False,
                                    )
                                )
                            elif msg_type == "get_translations":
                                body = data.get("data", {})
                                lang = body.get("lang", "en")
                                translations = self._get_translations(lang)
                                await ws.send(
                                    json.dumps(
                                        {"type": "translations", "data": {"lang": lang, "translations": translations}},
                                        ensure_ascii=False,
                                    )
                                )
                            elif msg_type == "save_channel_config":
                                body = data.get("data", {})
                                saved = self.user_manager.save_channel_config(
                                    user_id=user_id,
                                    channel_type=body.get("channel_type", ""),
                                    name=body.get("name", ""),
                                    config=body.get("config", {}) or {},
                                    account_id=body.get("account_id"),
                                    is_active=body.get("is_active", True),
                                )
                                if saved is None:
                                    await ws.send(json.dumps({"type": "channel_config_result", "data": {"ok": False, "error": "save_failed"}}, ensure_ascii=False))
                                else:
                                    # Dynamic load of channel instance
                                    if self.scheduler and self.scheduler.channel_manager:
                                        await self.scheduler.channel_manager.add_or_update_channel(user_id, saved["channel_type"], saved)
                                    await ws.send(json.dumps({"type": "channel_config_result", "data": {"ok": True, "config": saved}}, ensure_ascii=False))
                                    await ws.send(json.dumps(self._safe_get_channels_payload(user_id), ensure_ascii=False))
                            elif msg_type == "delete_channel_config":
                                body = data.get("data", {})
                                account_id = body.get("account_id", "")
                                channel_type = body.get("channel_type", "")
                                ok = self.user_manager.delete_channel_config(
                                    user_id=user_id,
                                    channel_type=channel_type,
                                    account_id=account_id,
                                )
                                if ok and self.scheduler and self.scheduler.channel_manager:
                                    await self.scheduler.channel_manager.remove_channel(user_id, channel_type, account_id)
                                await ws.send(json.dumps({"type": "channel_config_delete_result", "data": {"ok": ok}}, ensure_ascii=False))
                                await ws.send(json.dumps(self._safe_get_channels_payload(user_id), ensure_ascii=False))
                            elif msg_type == "set_channel_config_active":
                                body = data.get("data", {})
                                channel_type = body.get("channel_type", "")
                                account_id = body.get("account_id", "")
                                is_active = body.get("is_active", False)
                                updated = self.user_manager.set_channel_config_active(
                                    user_id=user_id,
                                    channel_type=channel_type,
                                    account_id=account_id,
                                    is_active=is_active,
                                )
                                # Dynamic channel change
                                if self.scheduler and self.scheduler.channel_manager:
                                    await self.scheduler.channel_manager.set_channel_active(user_id, channel_type, account_id, is_active)
                                await ws.send(
                                    json.dumps(
                                        {
                                            "type": "channel_config_state_result",
                                            "data": {"ok": updated is not None, "config": updated},
                                        },
                                        ensure_ascii=False,
                                    )
                                )
                                await ws.send(json.dumps(self._safe_get_channels_payload(user_id), ensure_ascii=False))
                            elif msg_type == "map_identity":
                                body = data.get("data", {})
                                mapped = self.user_manager.map_identity(
                                    user_id=user_id,
                                    channel=body.get("channel", ""),
                                    external_id=body.get("external_id", ""),
                                    alias=body.get("alias", ""),
                                    metadata=body.get("metadata", {}),
                                )
                                await ws.send(json.dumps({"type": "identity_map_result", "data": {"ok": mapped is not None, "mapping": mapped}}, ensure_ascii=False))
                                await ws.send(json.dumps(self._safe_get_channels_payload(user_id), ensure_ascii=False))
                            elif msg_type == "delete_identity_mapping":
                                body = data.get("data", {})
                                ok = self.user_manager.delete_identity_mapping(
                                    mapping_id=body.get("mapping_id", ""),
                                    user_id=user_id,
                                )
                                await ws.send(json.dumps({"type": "identity_delete_result", "data": {"ok": ok}}, ensure_ascii=False))
                                await ws.send(json.dumps(self._safe_get_channels_payload(user_id), ensure_ascii=False))
                            elif msg_type == "get_identity_mappings":
                                await ws.send(
                                    json.dumps(
                                        {
                                            "type": "identity_mappings",
                                            "mappings": self.user_manager.list_identity_mappings(user_id),
                                        },
                                        ensure_ascii=False,
                                    )
                                )
                            elif msg_type == "update_settings":
                                body = data.get("data", {})
                                provider_keys = body.get("provider_keys", {})
                                llm_routes = body.get("llm_routes", {})
                                success = True
                                error = None

                                try:
                                    from crabclaw.config.loader import load_config, save_config
                                    from crabclaw.config.schema import ProviderConfig
                                    config = load_config()

                                    # Handle provider keys update
                                    for provider_name, provider_data in provider_keys.items():
                                        if isinstance(provider_name, str) and provider_name.startswith("user:"):
                                            user_name = provider_name[len("user:"):].strip()
                                            if not user_name:
                                                success = False
                                                error = "Invalid user provider name"
                                                continue

                                            user_providers = getattr(config.providers, "user_providers", {}) or {}
                                            provider = user_providers.get(user_name) or ProviderConfig()

                                            if "api_key" in provider_data:
                                                provider.api_key = provider_data["api_key"]
                                            elif "apiKey" in provider_data:
                                                provider.api_key = provider_data["apiKey"]

                                            if "api_base" in provider_data:
                                                provider.api_base = provider_data["api_base"]
                                            elif "apiBase" in provider_data:
                                                provider.api_base = provider_data["apiBase"]

                                            if "model" in provider_data:
                                                provider.model = provider_data["model"]

                                            user_providers[user_name] = provider
                                            config.providers.user_providers = user_providers
                                            continue

                                        if hasattr(config.providers, provider_name):
                                            provider = getattr(config.providers, provider_name)
                                            if "api_key" in provider_data:
                                                provider.api_key = provider_data["api_key"]
                                            elif "apiKey" in provider_data:
                                                provider.api_key = provider_data["apiKey"]

                                            if "api_base" in provider_data:
                                                provider.api_base = provider_data["api_base"]
                                            elif "apiBase" in provider_data:
                                                provider.api_base = provider_data["apiBase"]

                                            if "model" in provider_data:
                                                provider.model = provider_data["model"]
                                        else:
                                            success = False
                                            error = f"Unknown provider key: {provider_name}"

                                    # Handle LLM routes update
                                    if llm_routes:
                                        if not hasattr(config, "llm_routes"):
                                            config.llm_routes = {}
                                        for callpoint, provider_name in llm_routes.items():
                                            if provider_name:
                                                config.llm_routes[callpoint] = provider_name
                                            else:
                                                # Remove the route if provider_name is empty
                                                config.llm_routes.pop(callpoint, None)
                                        logger.warning(f"Updated LLM routes: {llm_routes}")

                                    # Handle language update
                                    if "language" in body:
                                        config.language = body["language"]
                                        logger.warning(f"Updated language to: {config.language}")

                                    save_config(config)
                                    logger.warning(f"Updated provider settings for: {list(provider_keys.keys())}")

                                    # Update agent profile
                                    if self.scheduler:
                                        agent_keys = ["agent_name", "nickname", "gender", "age", "height", "weight", "hobbies"]
                                        if any(k in body for k in agent_keys):
                                            for k in agent_keys:
                                                if k in body:
                                                    if k in ["age", "height", "weight"]:
                                                        setattr(self.scheduler.state, k, float(body[k] or 0))
                                                    elif k == "hobbies":
                                                        hobbies = body[k]
                                                        if isinstance(hobbies, str):
                                                            hobbies = [h.strip() for h in hobbies.split(",") if h.strip()]
                                                        self.scheduler.state.hobbies = hobbies
                                                    else:
                                                        setattr(self.scheduler.state, k, body[k])

                                            if self.scheduler.sapiens_core and self.scheduler.sapiens_core.self_model:
                                                identity = self.scheduler.sapiens_core.self_model.identity
                                                for k in agent_keys:
                                                    if k in body:
                                                        if k == "age":
                                                            val = float(body[k] or 0)
                                                            identity["age"] = val
                                                            if hasattr(self.scheduler.sapiens_core, "physiology") and self.scheduler.sapiens_core.physiology:
                                                                p = self.scheduler.sapiens_core.physiology
                                                                if hasattr(p, "lifecycle"):
                                                                    p.lifecycle.age_ticks = int(val * p.lifecycle.TICK_PER_YEAR)
                                                        elif k in ["height", "weight"]:
                                                            identity[k] = float(body[k] or 0)
                                                        elif k == "hobbies":
                                                            hobbies = body[k]
                                                            if isinstance(hobbies, str):
                                                                hobbies = [h.strip() for h in hobbies.split(",") if h.strip()]
                                                            identity["hobbies"] = hobbies
                                                        else:
                                                            identity[k.replace("agent_", "")] = body[k]

                                            await self.broadcast_manager.publish(
                                                scope="system:state",
                                                message={"type": "internal_state", "data": self.scheduler.state.model_dump()}
                                            )

                                        # Handle push_interval update
                                        if "push_interval" in body:
                                            try:
                                                interval_val = float(body["push_interval"])
                                                self.scheduler.config.dashboard.state_push_interval_s = max(0.2, interval_val)
                                                logger.info(f"Updated state_push_interval_s to {self.scheduler.config.dashboard.state_push_interval_s}")
                                            except (ValueError, TypeError) as e:
                                                logger.warning(f"Invalid push_interval value: {body.get('push_interval')}, error: {e}")

                                        # Handle channel_mode update
                                        if "channel_mode" in body:
                                            mode = body["channel_mode"]
                                            if mode in ["multi", "single"]:
                                                config.channel_mode = mode
                                                save_config(config)
                                                logger.info(f"Updated channel_mode to {mode}")
                                            else:
                                                logger.warning(f"Invalid channel_mode value: {mode}")

                                except Exception as e:
                                    success = False
                                    error = str(e)
                                    logger.warning(f"Failed to update provider settings: {e}")

                                await ws.send(
                                    json.dumps(
                                        {
                                            "type": "update_settings_result",
                                            "data": {"success": success, "error": error},
                                        },
                                        ensure_ascii=False,
                                    )
                                )
                            elif msg_type == "test_provider":
                                body = data.get("data", {})
                                provider_id = body.get("provider_id", "")
                                # Support both camelCase and snake_case from frontend
                                api_key = body.get("api_key", "") or body.get("apiKey", "")
                                api_base = body.get("api_base", "") or body.get("apiBase", "")
                                model = body.get("model", "")
                                success = False
                                error = "Unknown error"

                                try:
                                    from crabclaw.providers.custom_provider import CustomProvider
                                    from crabclaw.providers.litellm_provider import LiteLLMProvider
                                    from crabclaw.providers.openai_codex_provider import (
                                        OpenAICodexProvider,
                                    )

                                    logger.warning(f"Received test_provider request: provider_id={provider_id}, api_key={api_key[:4]}..., api_base={api_base}, model={model}")

                                    # Log the test request details
                                    logger.warning(f"Testing provider: {provider_id}, api_key: {api_key[:4]}..., api_base: {api_base}, model: {model}")

                                    if provider_id == "custom" or (isinstance(provider_id, str) and provider_id.startswith("user:")):
                                        provider = CustomProvider(
                                            api_key=api_key,
                                            api_base=api_base or "http://localhost:8000/v1",
                                            default_model=model or "test",
                                        )
                                    elif provider_id == "openai_codex" or (model and model.startswith("openai-codex/")):
                                        provider = OpenAICodexProvider(default_model=model or "test")
                                    else:
                                        provider = LiteLLMProvider(
                                            api_key=api_key,
                                            api_base=api_base,
                                            default_model=model or "test",
                                            provider_name=provider_id,
                                        )

                                    # Try a simple completion to test the connection
                                    logger.warning(f"Testing connection with provider: {provider_id}")
                                    result = await provider.chat(
                                        messages= [{"role": "user", "content": "test"}],
                                        max_tokens=5,
                                    )
                                    if result and getattr(result, "finish_reason", None) != "error":
                                        success = True
                                        error = None
                                        logger.warning(f"Provider test successful for: {provider_id}")
                                    else:
                                        error = (getattr(result, "content", None) or "No response from provider") if result else "No response from provider"
                                        logger.warning(f"Provider test failed for {provider_id}: {error}")
                                except Exception as e:
                                    error = str(e)
                                    logger.warning(f"Provider test failed for {provider_id}: {e}")

                                logger.warning(f"Sending test_provider_result: success={success}, error={error}, provider_id={provider_id}")
                                await ws.send(
                                    json.dumps(
                                        {
                                            "type": "test_provider_result",
                                            "data": {"success": success, "error": error, "provider_id": provider_id},
                                        },
                                        ensure_ascii=False,
                                    )
                                )
                            elif msg_type == "get_files":
                                files = self._get_prompt_files()
                                await ws.send(
                                    json.dumps(
                                        {"type": "files", "data": {"files": files}},
                                        ensure_ascii=False,
                                    )
                                )
                            elif msg_type == "get_file_content":
                                file_name = data.get("data", {}).get("file_name", "")
                                content = self._get_file_content(file_name)
                                await ws.send(
                                    json.dumps(
                                        {"type": "file_content", "data": {"file_name": file_name, "content": content}},
                                        ensure_ascii=False,
                                    )
                                )
                            elif msg_type == "save_file":
                                file_data = data.get("data", {})
                                file_name = file_data.get("file_name", "")
                                content = file_data.get("content", "")
                                success = self._save_file(file_name, content)
                                await ws.send(
                                    json.dumps(
                                        {"type": "file_saved", "data": {"success": success, "file_name": file_name}},
                                        ensure_ascii=False,
                                    )
                                )

                            # ... other non-chat message types

                        except json.JSONDecodeError:
                            logger.warning(f"Invalid JSON received: {msg[:100]}")
                        except KeyError as e:
                            logger.warning(f"Missing expected field in message: {e}")
                        except Exception as e:
                            logger.error(f"Error processing message: {e}", exc_info=True)

                await asyncio.gather(broadcast_loop(), handle_messages())

            except ConnectionRefusedError as e:
                logger.warning(f"WebSocket connection refused: {e}")
                # The connection will be closed by the websockets library implicitly.

            except Exception as e:
                logger.error(f"WebSocket error for user '{user_id}': {e}", exc_info=True)

            finally:
                if user_id and q_user:
                    await self.broadcast_manager.unsubscribe(q_user, scope=user_id)
                if q_system:
                    await self.broadcast_manager.unsubscribe(q_system, scope="system:state")
                logger.info(f"WebSocket client disconnected for user '{user_id}'")

        self._ws_server = await serve(_handler, self.config.host, self.config.ws_port)
        logger.info("Dashboard WS serving %s", self.ws_url)
        await self._ws_server.wait_closed()

    def _get_providers(self) -> list:
        try:
            from crabclaw.config.loader import load_config
            config = load_config()
            from crabclaw.providers.registry import PROVIDERS

            providers = []
            for spec in PROVIDERS:
                p = getattr(config.providers, spec.name, None)
                if p is None:
                    continue

                # Check if provider is ready
                status = "error"
                if spec.is_oauth:
                    # For OAuth providers, check if they have valid token information
                    # We need to check if there's any stored token or auth information
                    # This is a simplified check - in a real scenario, we would validate the token
                    status = "ok" if hasattr(p, "token") and p.token else "error"
                else:
                    # For non-OAuth providers, require either api_key or api_base
                    # At least one of these should be present to consider it ready
                    status = "ok" if (p.api_key or p.api_base) else "error"

                # Get model: only use provider-specific model, no default fallback
                model = getattr(p, "model", "")

                providers.append({
                    "name": spec.label,
                    "config_name": spec.name,
                    "model": model,
                    "provider_model": model,  # For frontend compatibility
                    "api_base": getattr(p, "api_base", ""),
                    "api_key": getattr(p, "api_key", ""),
                    "status": status
                })

            user_providers = getattr(config.providers, "user_providers", {}) or {}
            for user_name, p in user_providers.items():
                status = "ok" if (getattr(p, "api_key", "") or getattr(p, "api_base", "")) else "error"
                model = getattr(p, "model", "") or ""
                providers.append(
                    {
                        "name": user_name,
                        "config_name": f"user:{user_name}",
                        "model": model,
                        "provider_model": model,
                        "api_base": getattr(p, "api_base", "") or "",
                        "api_key": getattr(p, "api_key", "") or "",
                        "status": status,
                    }
                )
            return providers
        except Exception as e:
            logger.error("Failed to get providers: %s", e)
            return [{"name": "Error", "status": "error", "model": str(e)}]

    def _get_skills(self) -> dict:
        """Get all available skills (built-in and workspace)."""
        try:
            from crabclaw.config.loader import load_config
            from crabclaw.agent.skills import SkillsLoader

            config = load_config()
            workspace = config.workspace_path

            # Get the built-in skills directory (crabclaw/skills)
            builtin_skills_dir = Path(__file__).parent.parent / "skills"

            # Create loader
            loader = SkillsLoader(workspace, builtin_skills_dir=builtin_skills_dir)

            # Get all skills without filtering
            all_skills = loader.list_skills(filter_unavailable=False)

            builtin_skills = []
            workspace_skills = []

            for skill in all_skills:
                meta = loader.get_skill_metadata(skill["name"]) or {}
                skill_info = {
                    "name": skill["name"],
                    "description": meta.get("description", ""),
                    "path": skill["path"],
                    "source": skill["source"]
                }
                if skill["source"] == "builtin":
                    builtin_skills.append(skill_info)
                else:
                    workspace_skills.append(skill_info)

            logger.warning(f"_get_skills: builtin={len(builtin_skills)}, workspace={len(workspace_skills)}")
            return {
                "built_in": builtin_skills,
                "workspace": workspace_skills
            }
        except Exception as e:
            logger.error(f"Failed to get skills: {e}")
            return {"built_in": [], "workspace": []}

    def _get_config(self) -> dict:
        try:
            from crabclaw.config.loader import load_config, get_config_path
            config = load_config()

            # Load raw config content
            raw_config_content = ""
            try:
                config_path = get_config_path()
                if config_path.exists():
                    raw_config_content = config_path.read_text(encoding="utf-8")
            except Exception as e:
                logger.warning(f"Failed to read raw config file: {e}")


            # Get providers catalog
            providers_catalog = []
            providers = self._get_providers()
            for p in providers:
                providers_catalog.append({
                    "config_name": p["config_name"],
                    "label": p["name"],
                    "model_name": p["model"],
                    "base_url": p["api_base"],
                    "api_key": p["api_key"],
                    "ready": p["status"] == "ok"
                })

            # Built-in LLM callpoints (program constants, not from config)
            llm_callpoints = [
                {
                    "key": "agent",
                    "label": "Agent 主对话",
                    "description": "核心对话入口（需要配置 provider）"
                },
                {
                    "key": "subagent",
                    "label": "Subagent 工具调用",
                    "description": "子代理/工具调用（需要配置 openai 工具模型）"
                },
                {
                    "key": "vision",
                    "label": "视觉处理",
                    "description": "处理图片和视觉相关任务"
                },
                {
                    "key": "transcribe_llm",
                    "label": "语音转录",
                    "description": "处理语音转文本任务"
                },
                {
                    "key": "memory_consolidation",
                    "label": "记忆整合",
                    "description": "处理长期记忆和知识整合"
                },
                {
                    "key": "sapiens_response",
                    "label": "Sapiens 响应",
                    "description": "Sapiens 组件的响应生成"
                },
                {
                    "key": "chat",
                    "label": "Dashboard 聊天",
                    "description": "Dashboard 内置聊天功能"
                }
            ]

            # Get LLM routes
            llm_routes = {}
            if hasattr(config, "llm_routes"):
                llm_routes = config.llm_routes

            # Channels are now managed per-user in workspace/portfolios.
            channels: list[str] = []

            # Get workspace safely
            workspace = ""
            try:
                workspace = str(config.workspace_path)
            except Exception as e:
                logger.warning("Failed to get workspace: %s", e)

            # Get model safely
            model = ""
            try:
                # Don't use config.agents.defaults.model, only use provider-specific models
                # model = config.agents.defaults.model
                pass
            except Exception as e:
                logger.warning("Failed to get model: %s", e)

            config_data = {
                "workspace": workspace,
                "model": model,
                "language": getattr(config, "language", "en"),
                "channels": channels,
                "providers_catalog": providers_catalog,
                "llm_callpoints": llm_callpoints,
                "llm_routes": llm_routes,
                "raw_config": raw_config_content
            }
            logger.debug("Get config: %s", config_data)
            return config_data
        except Exception as e:
            logger.error("Failed to get config: %s", e)
            # Return fallback data even on error
            return {
                "error": str(e),
                "workspace": "",
                "model": "",
                "language": "en",
                "channels": [],
                "providers_catalog": [],
                "llm_callpoints": [
                    {
                        "key": "agent",
                        "label": "Agent 主对话",
                        "description": "核心对话入口（需要配置 provider）"
                    },
                    {
                        "key": "subagent",
                        "label": "Subagent 工具调用",
                        "description": "子代理/工具调用（需要配置 openai 工具模型）"
                    },
                    {
                        "key": "vision",
                        "label": "视觉处理",
                        "description": "处理图片和视觉相关任务"
                    },
                    {
                        "key": "transcribe_llm",
                        "label": "语音转录",
                        "description": "处理语音转文本任务"
                    },
                    {
                        "key": "memory_consolidation",
                        "label": "记忆整合",
                        "description": "处理长期记忆和知识整合"
                    },
                    {
                        "key": "sapiens_response",
                        "label": "Sapiens 响应",
                        "description": "Sapiens 组件的响应生成"
                    },
                    {
                        "key": "chat",
                        "label": "Dashboard 聊天",
                        "description": "Dashboard 内置聊天功能"
                    }
                ],
                "llm_routes": {}
            }

    def _get_translations(self, lang: str) -> dict:
        """Get translations for a specific language."""
        try:
            from crabclaw.i18n.translator import Translator
            translator = Translator(lang)
            # Return the translations dict for the language
            return translator.translations.get(lang, {})
        except Exception as e:
            logger.error(f"Failed to load translations for {lang}: {e}")
            return {}

    def _get_channel_catalog(self) -> list[dict[str, Any]]:
        try:
            from crabclaw.config.schema import ChannelsConfig
            from crabclaw.channels.registry import discover_all

            def _safe_param_default(field_info: Any) -> Any:
                default_val = getattr(field_info, "default", None)

                # Pydantic required-field sentinel is not JSON serializable.
                if type(default_val).__name__ == "PydanticUndefinedType":
                    factory = getattr(field_info, "default_factory", None)
                    if callable(factory):
                        try:
                            default_val = factory()
                        except Exception:
                            return ""
                    else:
                        return ""

                if default_val is None:
                    return ""
                if isinstance(default_val, (str, int, float, bool, list, dict)):
                    return default_val
                if isinstance(default_val, (tuple, set)):
                    return list(default_val)
                if hasattr(default_val, "model_dump"):
                    try:
                        return default_val.model_dump(mode="json")
                    except Exception:
                        return str(default_val)

                try:
                    json.dumps(default_val, ensure_ascii=False)
                    return default_val
                except Exception:
                    return str(default_val)

            discovered = discover_all()
            channels = []
            for name, field in ChannelsConfig.model_fields.items():
                if name in {"send_progress", "send_tool_hints"}:
                    continue
                annotation = field.annotation
                parameters: dict[str, dict[str, Any]] = {}
                if hasattr(annotation, "model_fields"):
                    for p_name, p_field in annotation.model_fields.items():
                        if p_name == "enabled":
                            continue
                        p_type = str(getattr(p_field, "annotation", "str"))
                        description = getattr(p_field, "description", "") or ""
                        parameters[p_name] = {
                            "type": p_type.replace("typing.", ""),
                            "required": bool(getattr(p_field, "is_required", lambda: False)()),
                            "default": _safe_param_default(p_field),
                            "description": description,
                        }
                channel_cls = discovered.get(name)
                display_name = getattr(channel_cls, "display_name", name.replace("_", " ").title())
                description = (getattr(annotation, "__doc__", "") or "").strip() or f"{display_name} channel"
                channels.append(
                    {
                        "name": name,
                        "display_name": display_name,
                        "description": description,
                        "available": channel_cls is not None,
                        "parameters": parameters,
                    }
                )
            return channels
        except Exception as e:
            logger.error("Failed to build channel catalog: %s", e)
            return []

    def _get_channels_payload(self, user_id: str) -> dict[str, Any]:
        user_configs = self.user_manager.list_channel_configs(user_id)
        channels = self._get_channel_catalog()
        for item in channels:
            item["instance_count"] = len(user_configs.get(item.get("name", ""), []))
        return {
            "type": "channels",
            "data": {
                "channels": channels,
                "user_configs": user_configs,
                "identity_mappings": self.user_manager.list_identity_mappings(user_id),
                "storage_path": str(self.user_manager.get_portfolio_dir(user_id) / "channels"),
            },
        }

    def _safe_get_channels_payload(self, user_id: str) -> dict[str, Any]:
        try:
            return self._get_channels_payload(user_id)
        except Exception as e:
            logger.error("Failed to build channels payload for user %s: %s", user_id, e)
            storage_path = ""
            with contextlib.suppress(Exception):
                storage_path = str(self.user_manager.get_portfolio_dir(user_id) / "channels")
            return {
                "type": "channels",
                "data": {
                    "channels": [],
                    "user_configs": {},
                    "identity_mappings": [],
                    "storage_path": storage_path,
                    "error": str(e),
                },
            }

    def _get_workspace_path(self) -> str:
        try:
            from crabclaw.config.loader import load_config
            config = load_config()
            return str(config.workspace_path)
        except Exception:
            return ""

    def _get_prompt_files(self) -> list:
        try:
            from pathlib import Path
            import time
            workspace_path = self._get_workspace_path()
            if not workspace_path:
                return []

            workspace = Path(workspace_path)
            files = []

            # Directories to scan for md and py files
            dirs_to_scan = ["prompts", "memory", "social", "nature", "crabclaw"]

            for dir_name in dirs_to_scan:
                dir_path = workspace / dir_name
                if dir_path.exists() and dir_path.is_dir():
                    # Scan for .md files
                    for file_path in dir_path.glob("*.md"):
                        stat = file_path.stat()
                        files.append({
                            "name": f"{dir_name}/{file_path.name}",
                            "size": stat.st_size,
                            "mtime": stat.st_mtime
                        })
                    # Scan for .py files in crabclaw directory
                    if dir_name == "crabclaw":
                        for file_path in dir_path.rglob("*.py"):
                            # Only include files in specific subdirectories or key files
                            if any(part in str(file_path) for part in ["sapiens", "agent", "config", "providers"]):
                                stat = file_path.stat()
                                rel_path = file_path.relative_to(workspace)
                                files.append({
                                    "name": str(rel_path),
                                    "size": stat.st_size,
                                    "mtime": stat.st_mtime
                                })

            # Also load other md files from workspace root
            for file_path in workspace.glob("*.md"):
                stat = file_path.stat()
                files.append({
                    "name": file_path.name,
                    "size": stat.st_size,
                    "mtime": stat.st_mtime
                })

            return files
        except Exception:
            return []

    def _get_file_content(self, file_name: str) -> str:
        try:
            from pathlib import Path
            workspace_path = self._get_workspace_path()
            if not workspace_path:
                return ""

            workspace = Path(workspace_path)

            # Handle files with directory prefix (e.g., "memory/file.md" or "sapiens/agent.py")
            if "/" in file_name:
                file_path = workspace / file_name
                if file_path.exists() and file_path.suffix in [".md", ".py", ".txt", ".json"]:
                    return file_path.read_text(encoding="utf-8")

            # Try to find file in known directories
            for dir_name in ["prompts", "memory", "social", "nature"]:
                file_path = workspace / dir_name / file_name
                if file_path.exists() and file_path.suffix in [".md", ".py", ".txt", ".json"]:
                    return file_path.read_text(encoding="utf-8")

            # Then try workspace root
            file_path = workspace / file_name
            if file_path.exists() and file_path.suffix in [".md", ".py", ".txt", ".json"]:
                return file_path.read_text(encoding="utf-8")

            return ""
        except Exception:
            return ""

    def _save_file(self, file_name: str, content: str) -> bool:
        try:
            from pathlib import Path
            workspace_path = self._get_workspace_path()
            if not workspace_path:
                return False

            workspace = Path(workspace_path)

            # Handle files with directory prefix (e.g., "memory/file.md" or "sapiens/agent.py")
            if "/" in file_name:
                file_path = workspace / file_name
                if file_path.suffix in [".md", ".py", ".txt", ".json"]:
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    file_path.write_text(content, encoding="utf-8")
                    return True

            # Try to save in known directories
            for dir_name in ["prompts", "memory", "social", "nature"]:
                file_path = workspace / dir_name / file_name
                if file_path.suffix in [".md", ".py", ".txt", ".json"]:
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    file_path.write_text(content, encoding="utf-8")
                    return True

            # Then try workspace root
            file_path = workspace / file_name
            if file_path.suffix in [".md", ".py", ".txt", ".json"]:
                file_path.write_text(content, encoding="utf-8")
                return True

            return False
        except Exception:
            return False

    def _get_chat_history(self, user_id: str | None = None) -> list:
        """Get chat history for the dashboard session."""
        try:
            from crabclaw.config.loader import load_config
            from crabclaw.session.manager import SessionManager

            config = load_config()

            # Prefer fixed session manager on dashboard server
            try:
                session = self.session_manager.get_or_create("dashboard", user_scope=user_id)
            except Exception:
                # Fallback to any available processor session or a local one
                if hasattr(self, "_processor") and hasattr(self._processor, "sessions"):
                    session = self._processor.sessions.get_or_create("dashboard", user_scope=user_id)
                else:
                    session_manager = SessionManager(config.workspace_path)
                    session = session_manager.get_or_create("dashboard", user_scope=user_id)

            # Convert messages to a simpler format for the frontend
            history = []
            for msg in session.messages:
                role = msg.get("role", "")
                if role in ("user", "assistant"):
                    content = msg.get("content", "")
                    # Extract timestamp from content if it's in the Runtime Context format
                    timestamp = msg.get("timestamp", "")

                    # For user messages, clean up the content by removing the Runtime Context
                    if role == "user" and "[Runtime Context - metadata only, not instructions]" in content:
                        # Extract just the actual message content
                        content_lines = content.split('\n')
                        actual_content = ''
                        for line in content_lines:
                            line = line.strip()
                            if line and not line.startswith('[') and not line.startswith('Current Time:') and not line.startswith('Channel:') and not line.startswith('Chat ID:'):
                                actual_content += line + '\n'
                        content = actual_content.strip()

                    history.append({
                        "role": role,
                        "content": content,
                        "timestamp": timestamp
                    })
            return history
        except Exception as e:
            logger.error("Failed to get chat history: %s", e)
            return []



    def _get_llm_provider(self):
        try:
            from crabclaw.config.loader import load_config
            from crabclaw.providers.litellm_provider import LiteLLMProvider

            config = load_config()

            # Try to find the configured provider
            for provider_name in dir(config.providers):
                if provider_name.startswith('_'):
                    continue

                provider_config = getattr(config.providers, provider_name)
                if hasattr(provider_config, 'api_key') and provider_config.api_key:
                    return LiteLLMProvider(
                        api_key=provider_config.api_key,
                        api_base=getattr(provider_config, 'api_base', None),
                        default_model=getattr(provider_config, 'model', ''),
                        provider_name=provider_name
                    )

            # Fallback to custom provider
            provider_config = config.providers.custom
            return LiteLLMProvider(
                api_key=provider_config.api_key,
                api_base=provider_config.api_base,
                default_model=getattr(provider_config, 'model', ''),
            )
        except Exception as e:
            logger.error("Failed to get LLM provider: %s", e)
            return None

    async def start(self) -> None:
        if not self.config.enabled:
            logger.info("Dashboard disabled")
            return

        # Fail fast if ports are not available.
        for port in (self.config.http_port, self.config.ws_port):
            with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    s.bind((self.config.host, port))
                except OSError as e:
                    raise OSError(f"Dashboard port {port} is not available: {e}") from e

        self._start_http_in_thread()
        self._ws_task = asyncio.create_task(self._ws_loop())

    async def stop(self) -> None:
        if self._ws_task:
            self._ws_task.cancel()
            with contextlib.suppress(BaseException):
                await self._ws_task
            self._ws_task = None

        if self._ws_server:
            with contextlib.suppress(BaseException):
                self._ws_server.close()
                await self._ws_server.wait_closed()
            self._ws_server = None

        if self._httpd:
            with contextlib.suppress(BaseException):
                self._httpd.shutdown()
                self._httpd.server_close()
            self._httpd = None

        if self._http_thread:
            with contextlib.suppress(BaseException):
                self._http_thread.join(timeout=2.0)
            self._http_thread = None
