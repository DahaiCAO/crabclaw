"""
ClawSocial info tools - Get information about ClawSocial connections
"""
import logging
import json
from typing import Any, Optional
from dataclasses import asdict

from crabclaw.agent.tools.base import Tool
from .connection_manager import get_connection_manager

logger = logging.getLogger(__name__)


class ClawSocialListConnectionsTool(Tool):
    """List all ClawSocial connections and their status."""
    
    @property
    def name(self) -> str:
        return "clawsocial_list_connections"
    
    @property
    def description(self) -> str:
        return "List all configured ClawSocial connections with their status and basic information"
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }
    
    async def execute(self, **kwargs: Any) -> str:
        """Execute the tool."""
        try:
            manager = get_connection_manager()
            connections = manager.get_all_connections()
            
            result = {
                "success": True,
                "connections": []
            }
            
            for conn in connections:
                conn_info = {
                    "id": conn.conn_id,
                    "url": conn.url,
                    "name": conn.name,
                    "description": conn.description,
                    "status": conn.status,
                    "is_connected": conn.is_connected
                }
                
                if conn.info:
                    conn_info["info"] = asdict(conn.info)
                
                result["connections"].append(conn_info)
            
            logger.info(f"Listed {len(connections)} ClawSocial connections")
            return json.dumps(result, ensure_ascii=False)
            
        except Exception as e:
            logger.error(f"Failed to list ClawSocial connections: {e}")
            return json.dumps({
                "success": False,
                "error": str(e)
            }, ensure_ascii=False)


class ClawSocialGetInfoTool(Tool):
    """Get detailed information about a specific ClawSocial connection."""
    
    @property
    def name(self) -> str:
        return "clawsocial_get_info"
    
    @property
    def description(self) -> str:
        return "Get detailed information about a specific ClawSocial connection, including agent count, group count, etc."
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "connection_id": {"type": "string", "description": "Optional ID of the connection to get info for. If not provided, returns info for all connected connections."}
            },
            "required": [],
        }
    
    async def execute(self, connection_id: Optional[str] = None, **kwargs: Any) -> str:
        """Execute the tool."""
        try:
            manager = get_connection_manager()
            
            if connection_id:
                conn = manager.get_connection(connection_id)
                if not conn:
                    return json.dumps({
                        "success": False,
                        "error": f"Connection not found: {connection_id}"
                    }, ensure_ascii=False)
                
                return json.dumps({
                    "success": True,
                    "connection": {
                        "id": conn.conn_id,
                        "url": conn.url,
                        "name": conn.name,
                        "description": conn.description,
                        "status": conn.status,
                        "is_connected": conn.is_connected,
                        "info": asdict(conn.info) if conn.info else None
                    }
                }, ensure_ascii=False)
            else:
                connected_conns = manager.get_connected_connections()
                return json.dumps({
                    "success": True,
                    "connections": [
                        {
                            "id": conn.conn_id,
                            "url": conn.url,
                            "name": conn.name,
                            "description": conn.description,
                            "status": conn.status,
                            "is_connected": conn.is_connected,
                            "info": asdict(conn.info) if conn.info else None
                        }
                        for conn in connected_conns
                    ]
                }, ensure_ascii=False)
            
        except Exception as e:
            logger.error(f"Failed to get ClawSocial info: {e}")
            return json.dumps({
                "success": False,
                "error": str(e)
            }, ensure_ascii=False)


class ClawSocialConnectTool(Tool):
    """Connect to ClawSocial instances."""
    
    @property
    def name(self) -> str:
        return "clawsocial_connect"
    
    @property
    def description(self) -> str:
        return "Connect to one or all configured ClawSocial instances"
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "connection_id": {"type": "string", "description": "Optional ID of the connection to connect to. If not provided, connects to all enabled connections."}
            },
            "required": [],
        }
    
    async def execute(self, connection_id: Optional[str] = None, **kwargs: Any) -> str:
        """Execute the tool."""
        try:
            manager = get_connection_manager()
            
            if connection_id:
                conn = manager.get_connection(connection_id)
                if not conn:
                    return json.dumps({
                        "success": False,
                        "error": f"Connection not found: {connection_id}"
                    }, ensure_ascii=False)
                
                success = await conn.connect()
                return json.dumps({
                    "success": success,
                    "connection_id": connection_id,
                    "message": "Connected successfully" if success else "Connection failed"
                }, ensure_ascii=False)
            else:
                results = await manager.connect_all()
                success_count = sum(1 for v in results.values() if v)
                return json.dumps({
                    "success": True,
                    "results": results,
                    "summary": f"Connected to {success_count}/{len(results)} ClawSocial instances"
                }, ensure_ascii=False)
            
        except Exception as e:
            logger.error(f"Failed to connect ClawSocial: {e}")
            return json.dumps({
                "success": False,
                "error": str(e)
            }, ensure_ascii=False)


class ClawSocialDisconnectTool(Tool):
    """Disconnect from ClawSocial instances."""
    
    @property
    def name(self) -> str:
        return "clawsocial_disconnect"
    
    @property
    def description(self) -> str:
        return "Disconnect from one or all ClawSocial instances"
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "connection_id": {"type": "string", "description": "Optional ID of the connection to disconnect from. If not provided, disconnects from all connections."}
            },
            "required": [],
        }
    
    async def execute(self, connection_id: Optional[str] = None, **kwargs: Any) -> str:
        """Execute the tool."""
        try:
            manager = get_connection_manager()
            
            if connection_id:
                conn = manager.get_connection(connection_id)
                if not conn:
                    return json.dumps({
                        "success": False,
                        "error": f"Connection not found: {connection_id}"
                    }, ensure_ascii=False)
                
                await conn.disconnect()
                return json.dumps({
                    "success": True,
                    "connection_id": connection_id,
                    "message": "Disconnected successfully"
                }, ensure_ascii=False)
            else:
                await manager.disconnect_all()
                return json.dumps({
                    "success": True,
                    "message": "Disconnected from all ClawSocial instances"
                }, ensure_ascii=False)
            
        except Exception as e:
            logger.error(f"Failed to disconnect ClawSocial: {e}")
            return json.dumps({
                "success": False,
                "error": str(e)
            }, ensure_ascii=False)
