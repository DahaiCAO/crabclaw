"""
仪表盘数据广播器

提供一个异步的发布/订阅机制，用于将 Agent 的内部状态和事件
安全地广播给仪表盘的 WebSocket 服务器。
"""
import asyncio
from typing import Any, Dict


class DashboardBroadcaster:
    """
    一个简单的异步发布/订阅广播器。
    """
    def __init__(self):
        self._subscribers = []

    async def subscribe(self, queue: asyncio.Queue):
        """订阅者提供一个队列来接收消息。"""
        self._subscribers.append(queue)

    def unsubscribe(self, queue: asyncio.Queue):
        """取消订阅。"""
        self._subscribers.remove(queue)

    async def publish(self, message: Dict[str, Any]):
        """向所有订阅者发布一条消息。"""
        for queue in self._subscribers:
            await queue.put(message)
