"""
ClawSocial Connection Manager

Manages multiple ClawSocial connections and provides access to their information.
"""
import asyncio
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from .config import config as clawsocial_config

logger = logging.getLogger(__name__)


@dataclass
class ClawSocialInfo:
    """Information about a ClawSocial instance."""
    conn_id: str
    url: str
    name: str = ""
    agent_count: int = 0
    group_count: int = 0
    private_chat_count: int = 0
    organization_count: int = 0
    status: str = "unknown"
    description: str = ""
    is_connected: bool = False


class ClawSocialConnection:
    """Represents a single ClawSocial connection."""
    
    def __init__(self, conn_id: str, config: Dict[str, Any]):
        self.conn_id = conn_id
        self.url = config.get("url", "")
        self.name = config.get("name", conn_id)
        self.description = config.get("description", "")
        self.status = config.get("status", "unknown")
        self.info: Optional[ClawSocialInfo] = None
        self.is_connected = False
    
    async def connect(self) -> bool:
        """Connect to this ClawSocial instance and fetch info."""
        try:
            logger.info(f"Connecting to ClawSocial: {self.conn_id} at {self.url}")
            
            # TODO: 实际连接逻辑需要根据 ClawSocial API 实现
            # 这里先模拟连接成功
            self.is_connected = True
            
            # 构建基本信息
            self.info = ClawSocialInfo(
                conn_id=self.conn_id,
                url=self.url,
                name=self.name,
                description=self.description,
                status=self.status,
                is_connected=True
            )
            
            # TODO: 从 API 获取实际数据
            # await self._fetch_info()
            
            logger.info(f"Connected to ClawSocial: {self.conn_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to {self.conn_id}: {e}")
            self.is_connected = False
            return False
    
    async def disconnect(self):
        """Disconnect from this ClawSocial instance."""
        try:
            logger.info(f"Disconnecting from ClawSocial: {self.conn_id}")
            self.is_connected = False
            if self.info:
                self.info.is_connected = False
        except Exception as e:
            logger.error(f"Error disconnecting from {self.conn_id}: {e}")
    
    async def _fetch_info(self):
        """Fetch actual info from ClawSocial API."""
        # TODO: 实现实际的 API 调用
        # 这里只是示例结构
        pass


class ClawSocialConnectionManager:
    """Manages multiple ClawSocial connections."""
    
    def __init__(self):
        self.connections: Dict[str, ClawSocialConnection] = {}
        self._is_running = False
    
    def load_connections(self):
        """Load connections from config."""
        enabled_conns = clawsocial_config.enabled_connections
        
        for conn_id, conn_config in enabled_conns.items():
            if conn_id not in self.connections:
                self.connections[conn_id] = ClawSocialConnection(conn_id, conn_config)
                logger.info(f"Loaded ClawSocial connection: {conn_id}")
        
        # 移除不再存在的连接
        for conn_id in list(self.connections.keys()):
            if conn_id not in enabled_conns:
                del self.connections[conn_id]
                logger.info(f"Removed ClawSocial connection: {conn_id}")
    
    async def connect_all(self) -> Dict[str, bool]:
        """Connect to all enabled ClawSocial instances."""
        self.load_connections()
        
        results = {}
        tasks = []
        
        for conn_id, conn in self.connections.items():
            tasks.append(self._connect_single(conn_id, conn))
        
        if tasks:
            completed = await asyncio.gather(*tasks, return_exceptions=True)
            for i, (conn_id, _) in enumerate(self.connections.items()):
                if isinstance(completed[i], Exception):
                    results[conn_id] = False
                    logger.error(f"Failed to connect {conn_id}: {completed[i]}")
                else:
                    results[conn_id] = completed[i]
        
        self._is_running = True
        return results
    
    async def _connect_single(self, conn_id: str, conn: ClawSocialConnection) -> bool:
        """Connect to a single ClawSocial instance."""
        return await conn.connect()
    
    async def disconnect_all(self):
        """Disconnect from all ClawSocial instances."""
        self._is_running = False
        
        tasks = []
        for conn in self.connections.values():
            tasks.append(conn.disconnect())
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    def get_connection(self, conn_id: str) -> Optional[ClawSocialConnection]:
        """Get a specific connection by ID."""
        return self.connections.get(conn_id)
    
    def get_all_connections(self) -> List[ClawSocialConnection]:
        """Get all loaded connections."""
        return list(self.connections.values())
    
    def get_connected_connections(self) -> List[ClawSocialConnection]:
        """Get all currently connected connections."""
        return [conn for conn in self.connections.values() if conn.is_connected]
    
    def get_all_info(self) -> List[ClawSocialInfo]:
        """Get info for all connections."""
        return [conn.info for conn in self.connections.values() if conn.info]
    
    def refresh_config(self):
        """Refresh configuration and reload connections."""
        clawsocial_config.refresh_config()
        self.load_connections()


# Global connection manager instance
_connection_manager: Optional[ClawSocialConnectionManager] = None


def get_connection_manager() -> ClawSocialConnectionManager:
    """Get the global connection manager instance."""
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = ClawSocialConnectionManager()
    return _connection_manager
