from __future__ import annotations

import contextlib
import json
import socket
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from loguru import logger


@dataclass
class GatewayServerConfig:
    enabled: bool = True
    host: str = "0.0.0.0"
    port: int = 18790


class GatewayServer:
    def __init__(self, config: GatewayServerConfig | None = None) -> None:
        self.config = config or GatewayServerConfig()
        self._httpd: ThreadingHTTPServer | None = None
        self._http_thread: threading.Thread | None = None

    @property
    def http_url(self) -> str:
        return f"http://{self.config.host}:{self.config.port}/"

    def _start_http_in_thread(self) -> None:
        parent = self

        class _Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
                logger.debug("Gateway HTTP: " + format, *args)

            def _send_json(self, code: int, payload: dict[str, Any]) -> None:
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self) -> None:  # noqa: N802
                if self.path in {"/", "/health", "/healthz"}:
                    return self._send_json(200, {"ok": True, "service": "crabclaw-gateway", "url": parent.http_url})
                return self._send_json(404, {"ok": False, "error": "not_found"})

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

        self._start_http_in_thread()

    async def stop(self) -> None:
        if self._httpd:
            with contextlib.suppress(BaseException):
                self._httpd.shutdown()
                self._httpd.server_close()
            self._httpd = None
