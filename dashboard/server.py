"""
仪表盘 Web 服务器

使用 FastAPI 和 WebSockets 为前端提供实时状态更新。
"""
import asyncio
import json
import logging
from typing import Any, Dict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from crabclaw.dashboard.broadcaster import DashboardBroadcaster

logger = logging.getLogger(__name__)


class DashboardServer:
    """
    管理 FastAPI 应用和 WebSocket 连接。
    """
    def __init__(self, broadcaster: DashboardBroadcaster, host: str, port: int):
        self.broadcaster = broadcaster
        self.host = host
        self.port = port
        self.app = FastAPI()
        self._server_task: asyncio.Task | None = None

        @self.app.websocket("/ws/status")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            queue = asyncio.Queue()
            await self.broadcaster.subscribe(queue)
            
            logger.info("Dashboard client connected.")
            try:
                while True:
                    message = await queue.get()
                    await websocket.send_json(message)
            except WebSocketDisconnect:
                logger.info("Dashboard client disconnected.")
            finally:
                self.broadcaster.unsubscribe(queue)

    async def start(self):
        """在 uvicorn 中启动 FastAPI 服务器。"""
        import uvicorn
        config = uvicorn.Config(self.app, host=self.host, port=self.port, log_level="warning")
        server = uvicorn.Server(config)
        
        logger.info(f"Dashboard server starting at http://{self.host}:{self.port}")
        self._server_task = asyncio.create_task(server.serve())

    def stop(self):
        """停止服务器任务。"""
        if self._server_task and not self._server_task.done():
            self._server_task.cancel()
            logger.info("Dashboard server stopped.")
