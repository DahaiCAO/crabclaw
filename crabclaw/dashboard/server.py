from __future__ import annotations

import asyncio
import contextlib
import json
import socket
import threading
from dataclasses import dataclass
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from loguru import logger
from websockets.server import serve

from crabclaw.dashboard.broadcaster import DashboardBroadcaster


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
        broadcaster: DashboardBroadcaster,
        *,
        static_dir: Path,
        config: DashboardConfig | None = None,
    ) -> None:
        self.broadcaster = broadcaster
        self.static_dir = static_dir
        self.config = config or DashboardConfig()

        self._httpd: ThreadingHTTPServer | None = None
        self._http_thread: threading.Thread | None = None
        self._ws_server: Any | None = None
        self._ws_task: asyncio.Task | None = None

    @property
    def http_url(self) -> str:
        return f"http://{self.config.host}:{self.config.http_port}/"

    @property
    def ws_url(self) -> str:
        return f"ws://{self.config.host}:{self.config.ws_port}/ws"

    def _start_http_in_thread(self) -> None:
        class _Handler(SimpleHTTPRequestHandler):
            def log_message(self, format: str, *args) -> None:  # noqa: A002
                logger.debug("Dashboard HTTP: " + format, *args)

        def _serve() -> None:
            try:
                self._httpd = ThreadingHTTPServer(
                    (self.config.host, self.config.http_port),
                    lambda *a, **kw: _Handler(*a, directory=str(self.static_dir), **kw),
                )
                logger.info("Dashboard HTTP serving {}", self.http_url)
                self._httpd.serve_forever(poll_interval=0.5)
            except Exception as e:
                logger.error("Dashboard HTTP server failed: {}", e)

        self._http_thread = threading.Thread(target=_serve, name="dashboard-http", daemon=True)
        self._http_thread.start()

    async def _ws_loop(self) -> None:
        async def _handler(ws) -> None:
            q = await self.broadcaster.register()
            try:
                await ws.send(json.dumps({"type": "hello", "data": {"ws": self.ws_url}}, ensure_ascii=False))
                
                async def broadcast_loop():
                    while True:
                        msg = await q.get()
                        await ws.send(msg)
                
                async def handle_messages():
                    async for msg in ws:
                        try:
                            data = json.loads(msg)
                            msg_type = data.get("type")
                            
                            if msg_type == "get_providers":
                                providers = self._get_providers()
                                await ws.send(json.dumps({
                                    "type": "providers",
                                    "data": {"providers": providers}
                                }, ensure_ascii=False))
                            
                            elif msg_type == "get_config":
                                config_data = self._get_config()
                                await ws.send(json.dumps({
                                    "type": "config",
                                    "data": config_data
                                }, ensure_ascii=False))
                            
                            elif msg_type == "chat_message":
                                chat_data = data.get("data", {})
                                response = await self._process_chat_message(chat_data.get("message", ""))
                                await ws.send(json.dumps({
                                    "type": "chat_response",
                                    "data": {"response": response}
                                }, ensure_ascii=False))
                            
                            elif msg_type == "get_files":
                                files = self._get_prompt_files()
                                await ws.send(json.dumps({
                                    "type": "files",
                                    "data": {"files": files}
                                }, ensure_ascii=False))
                            
                            elif msg_type == "get_file_content":
                                file_name = data.get("data", {}).get("file_name", "")
                                content = self._get_file_content(file_name)
                                await ws.send(json.dumps({
                                    "type": "file_content",
                                    "data": {"file_name": file_name, "content": content}
                                }, ensure_ascii=False))
                            
                            elif msg_type == "save_file":
                                file_name = data.get("data", {}).get("file_name", "")
                                content = data.get("data", {}).get("content", "")
                                success = self._save_file(file_name, content)
                                await ws.send(json.dumps({
                                    "type": "file_saved",
                                    "data": {"file_name": file_name, "success": success}
                                }, ensure_ascii=False))
                                
                        except json.JSONDecodeError:
                            pass
                
                await asyncio.gather(broadcast_loop(), handle_messages())
                
            except Exception:
                pass
            finally:
                await self.broadcaster.unregister(q)

        self._ws_server = await serve(_handler, self.config.host, self.config.ws_port)
        logger.info("Dashboard WS serving {}", self.ws_url)
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
                status = "ok" if (p.api_key or spec.is_oauth or p.api_base) else "error"
                providers.append({
                    "name": spec.label,
                    "model": getattr(p, "model", ""),
                    "status": status
                })
            return providers
        except Exception as e:
            logger.error("Failed to get providers: {}", e)
            return [{"name": "Error", "status": "error", "model": str(e)}]
    
    def _get_config(self) -> dict:
        try:
            from crabclaw.config.loader import load_config
            config = load_config()
            return {
                "workspace": str(config.workspace_path),
                "model": config.agents.defaults.model,
                "language": getattr(config, "language", "en"),
                "channels": list(config.channels.enabled) if hasattr(config, "channels") else [],
            }
        except Exception as e:
            return {"error": str(e)}
    
    def _get_workspace_path(self) -> str:
        try:
            from crabclaw.config.loader import load_config
            config = load_config()
            return str(config.workspace_path)
        except Exception as e:
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
        except Exception as e:
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
        except Exception as e:
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
        except Exception as e:
            return False
    
    async def _process_chat_message(self, message: str) -> str:
        try:
            from crabclaw.agent.loop import AgentLoop
            from crabclaw.bus.events import InboundMessage
            from crabclaw.bus.queue import MessageBus
            from crabclaw.config.loader import load_config
            
            # Create persistent bus and loop instances once
            if not hasattr(self, "_bus") or not hasattr(self, "_loop"):
                config = load_config()
                self._bus = MessageBus()
                self._loop = AgentLoop(
                    bus=self._bus,
                    provider=self._get_llm_provider(),
                    workspace=config.workspace_path,
                )
            
            inbound = InboundMessage(
                channel="dashboard",
                sender_id="dashboard_user",
                chat_id="dashboard",
                content=message,
            )
            
            # Use process_direct instead of process_message
            response = await self._loop.process_direct(
                content=message,
                session_key="dashboard",
                channel="dashboard"
            )
            return response.content if response else "No response"
        except Exception as e:
            logger.error("Chat processing error: {}", e)
            return f"Error: {str(e)}"
    
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
            logger.error("Failed to get LLM provider: {}", e)
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

