from __future__ import annotations

import asyncio
import contextlib
import json
import socket
import threading
import time
from dataclasses import dataclass
from http.cookies import SimpleCookie
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from clawlink.security import TokenError, decode_token, issue_token
from loguru import logger
from websockets.server import serve

from crabclaw.bus.broadcaster import BroadcastManager
from crabclaw.user.manager import UserManager


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
    ) -> None:
        self.broadcast_manager = broadcast_manager
        self.static_dir = static_dir
        self.config = config or DashboardConfig()
        self._jwt_keys = self._get_jwt_keys()
        self.workspace = workspace or self._resolve_workspace()
        self.user_manager = UserManager(self.workspace)

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
            if hasattr(config, "security") and hasattr(config.security, "jwt_keys"):
                return config.security.jwt_keys
            # Fallback for older configs or different structures
            if hasattr(config, "jwt_keys") and isinstance(config.jwt_keys, dict):
                 return config.jwt_keys
            return {}
        except Exception as e:
            logger.error(f"Could not load JWT keys from config: {e}")
            return {}

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
                q = await self.broadcast_manager.subscribe(scope=user_id)
                logger.info(f"WebSocket client connected for user '{user_id}'")

                await ws.send(json.dumps({"type": "hello", "data": {"ws": self.ws_url, "user_id": user_id}}, ensure_ascii=False))
                await ws.send(json.dumps({"type": "chat_history", "messages": self._get_chat_history(user_id)}, ensure_ascii=False))

                async def broadcast_loop():
                    while True:
                        msg = await q.get()
                        await ws.send(json.dumps(msg, ensure_ascii=False))

                async def handle_messages():
                    async for msg in ws:
                        try:
                            data = json.loads(msg)
                            msg_type = data.get("type")

                            if msg_type == "chat_message":
                                chat_data = data.get("data", {})
                                message_content = chat_data.get("message", "")
                                if message_content:
                                    broadcast_message = {
                                        "type": "user_message",
                                        "source_channel": "dashboard",
                                        "chat_id": "direct",
                                        "sender_id": user_id, # Authenticated user ID
                                        "content": message_content,
                                        "timestamp": time.time()
                                    }
                                    await self.broadcast_manager.publish(scope=user_id, message=broadcast_message)
                            elif msg_type == "get_channels":
                                await ws.send(json.dumps(self._get_channels_payload(user_id), ensure_ascii=False))
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
                                    await ws.send(json.dumps({"type": "channel_config_result", "ok": False, "error": "save_failed"}, ensure_ascii=False))
                                else:
                                    await ws.send(json.dumps({"type": "channel_config_result", "ok": True, "config": saved}, ensure_ascii=False))
                                    await ws.send(json.dumps(self._get_channels_payload(user_id), ensure_ascii=False))
                            elif msg_type == "delete_channel_config":
                                body = data.get("data", {})
                                ok = self.user_manager.delete_channel_config(
                                    user_id=user_id,
                                    channel_type=body.get("channel_type", ""),
                                    account_id=body.get("account_id", ""),
                                )
                                await ws.send(json.dumps({"type": "channel_config_delete_result", "ok": ok}, ensure_ascii=False))
                                await ws.send(json.dumps(self._get_channels_payload(user_id), ensure_ascii=False))
                            elif msg_type == "map_identity":
                                body = data.get("data", {})
                                mapped = self.user_manager.map_identity(
                                    user_id=user_id,
                                    channel=body.get("channel", ""),
                                    external_id=body.get("external_id", ""),
                                    alias=body.get("alias", ""),
                                    metadata=body.get("metadata", {}),
                                )
                                await ws.send(json.dumps({"type": "identity_map_result", "ok": mapped is not None, "mapping": mapped}, ensure_ascii=False))
                                await ws.send(json.dumps(self._get_channels_payload(user_id), ensure_ascii=False))
                            elif msg_type == "delete_identity_mapping":
                                body = data.get("data", {})
                                ok = self.user_manager.delete_identity_mapping(
                                    mapping_id=body.get("mapping_id", ""),
                                    user_id=user_id,
                                )
                                await ws.send(json.dumps({"type": "identity_delete_result", "ok": ok}, ensure_ascii=False))
                                await ws.send(json.dumps(self._get_channels_payload(user_id), ensure_ascii=False))
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

                            # ... other non-chat message types

                        except json.JSONDecodeError:
                            pass

                await asyncio.gather(broadcast_loop(), handle_messages())

            except ConnectionRefusedError as e:
                logger.warning(f"WebSocket connection refused: {e}")
                # The connection will be closed by the websockets library implicitly.

            except Exception as e:
                logger.error(f"WebSocket error for user '{user_id}': {e}", exc_info=True)

            finally:
                if user_id and q:
                    await self.broadcast_manager.unsubscribe(q, scope=user_id)
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

                providers.append({
                    "name": spec.label,
                    "config_name": spec.name,
                    "model": getattr(p, "model", ""),
                    "api_base": getattr(p, "api_base", ""),
                    "api_key": getattr(p, "api_key", ""),
                    "status": status
                })
            return providers
        except Exception as e:
            logger.error("Failed to get providers: %s", e)
            return [{"name": "Error", "status": "error", "model": str(e)}]

    def _get_config(self) -> dict:
        try:
            from crabclaw.config.loader import load_config
            config = load_config()

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

            # Get channels safely
            channels = []
            try:
                if hasattr(config, "channels") and hasattr(config.channels, "enabled"):
                    channels = list(config.channels.enabled)
            except Exception as e:
                logger.warning("Failed to get channels: %s", e)

            # Get workspace safely
            workspace = ""
            try:
                workspace = str(config.workspace_path)
            except Exception as e:
                logger.warning("Failed to get workspace: %s", e)

            # Get model safely
            model = ""
            try:
                model = config.agents.defaults.model
            except Exception as e:
                logger.warning("Failed to get model: %s", e)

            config_data = {
                "workspace": workspace,
                "model": model,
                "language": getattr(config, "language", "en"),
                "channels": channels,
                "providers_catalog": providers_catalog,
                "llm_callpoints": llm_callpoints,
                "llm_routes": llm_routes
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

    def _get_channel_catalog(self) -> list[dict[str, Any]]:
        try:
            from crabclaw.config.schema import ChannelsConfig

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
                        default_val = getattr(p_field, "default", None)
                        description = getattr(p_field, "description", "") or ""
                        parameters[p_name] = {
                            "type": p_type.replace("typing.", ""),
                            "required": bool(getattr(p_field, "is_required", lambda: False)()),
                            "default": default_val if default_val is not None else "",
                            "description": description,
                        }
                channels.append(
                    {
                        "name": name,
                        "display_name": name.title(),
                        "description": f"{name.title()} channel",
                        "available": True,
                        "parameters": parameters,
                    }
                )
            return channels
        except Exception as e:
            logger.error("Failed to build channel catalog: %s", e)
            return []

    def _get_channels_payload(self, user_id: str) -> dict[str, Any]:
        return {
            "type": "channels",
            "channels": self._get_channel_catalog(),
            "user_configs": self.user_manager.list_channel_configs(user_id),
            "identity_mappings": self.user_manager.list_identity_mappings(user_id),
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
            workspace_path = self._get_workspace_path()
            if not workspace_path:
                return []

            workspace = Path(workspace_path)
            prompts_dir = workspace / "prompts"
            files = []

            # Load files from workspace/prompts
            if prompts_dir.exists():
                for file_path in prompts_dir.glob("*.md"):
                    files.append({
                        "name": file_path.name,
                        "size": file_path.stat().st_size
                    })

            # Also load other md files from workspace root
            for file_path in workspace.glob("*.md"):
                files.append({
                    "name": file_path.name,
                    "size": file_path.stat().st_size
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

            # Try to find file in workspace/prompts first
            file_path = workspace / "prompts" / file_name
            if file_path.exists() and file_path.suffix == ".md":
                return file_path.read_text(encoding="utf-8")

            # Then try workspace root
            file_path = workspace / file_name
            if file_path.exists() and file_path.suffix == ".md":
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

            # Try to save in workspace/prompts first
            file_path = workspace / "prompts" / file_name
            if file_path.suffix == ".md":
                file_path.parent.mkdir(exist_ok=True)
                file_path.write_text(content, encoding="utf-8")
                return True

            # Then try workspace root
            file_path = workspace / file_name
            if file_path.suffix == ".md":
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

            # Use the same session manager as the AgentLoop if available
            # Note: The session key must match what process_direct uses
            # In process_direct, session_key becomes the session key directly
            if hasattr(self, "_processor") and hasattr(self._processor, "sessions"):
                session = self._processor.sessions.get_or_create("dashboard", user_scope=user_id)
            else:
                # Fallback to creating a new session manager
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
                        default_model=config.agents.defaults.model,
                        provider_name=provider_name
                    )

            # Fallback to custom provider
            provider_config = config.providers.custom
            return LiteLLMProvider(
                api_key=provider_config.api_key,
                api_base=provider_config.api_base,
                default_model=config.agents.defaults.model,
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
            self._ws_server = None

        if self._httpd:
            with contextlib.suppress(BaseException):
                self._httpd.shutdown()
                self._httpd.server_close()
            self._httpd = None
