"""
ClawSocial info tools - Get information about ClawSocial connections
"""
import logging
from typing import List, Dict, Any, Optional
from dataclasses import asdict

from crabclaw.agent.tools.base import Tool
from .connection_manager import get_connection_manager, ClawSocialInfo

logger = logging.getLogger(__name__)


class ClawSocialListConnectionsTool(Tool):
    """List all ClawSocial connections and their status."""
    
    name: str = "clawsocial_list_connections"
    description: str = "List all configured ClawSocial connections with their status and basic information"
    
    async def execute(self) -> Dict[str, Any]:
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
            return result
            
        except Exception as e:
            logger.error(f"Failed to list ClawSocial connections: {e}")
            return {
                "success": False,
                "error": str(e)
            }


class ClawSocialGetInfoTool(Tool):
    """Get detailed information about a specific ClawSocial connection."""
    
    name: str = "clawsocial_get_info"
    description: str = "Get detailed information about a specific ClawSocial connection, including agent count, group count, etc."
    
    async def execute(self, connection_id: Optional[str] = None) -> Dict[str, Any]:
        """Execute the tool.
        
        Args:
            connection_id: Optional ID of the connection to get info for.
                          If not provided, returns info for all connected connections.
        """
        try:
            manager = get_connection_manager()
            
            if connection_id:
                conn = manager.get_connection(connection_id)
                if not conn:
                    return {
                        "success": False,
                        "error": f"Connection not found: {connection_id}"
                    }
                
                return {
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
                }
            else:
                connected_conns = manager.get_connected_connections()
                return {
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
                }
            
        except Exception as e:
            logger.error(f"Failed to get ClawSocial info: {e}")
            return {
                "success": False,
                "error": str(e)
            }


class ClawSocialConnectTool(Tool):
    """Connect to ClawSocial instances."""
    
    name: str = "clawsocial_connect"
    description: str = "Connect to one or all configured ClawSocial instances"
    
    async def execute(self, connection_id: Optional[str] = None) -> Dict[str, Any]:
        """Execute the tool.
        
        Args:
            connection_id: Optional ID of the connection to connect to.
                          If not provided, connects to all enabled connections.
        """
        try:
            manager = get_connection_manager()
            
            if connection_id:
                conn = manager.get_connection(connection_id)
                if not conn:
                    return {
                        "success": False,
                        "error": f"Connection not found: {connection_id}"
                    }
                
                success = await conn.connect()
                return {
                    "success": success,
                    "connection_id": connection_id,
                    "message": "Connected successfully" if success else "Connection failed"
                }
            else:
                results = await manager.connect_all()
                success_count = sum(1 for v in results.values() if v)
                return {
                    "success": True,
                    "results": results,
                    "summary": f"Connected to {success_count}/{len(results)} ClawSocial instances"
                }
            
        except Exception as e:
            logger.error(f"Failed to connect ClawSocial: {e}")
            return {
                "success": False,
                "error": str(e)
            }


class ClawSocialDisconnectTool(Tool):
    """Disconnect from ClawSocial instances."""
    
    name: str = "clawsocial_disconnect"
    description: str = "Disconnect from one or all ClawSocial instances"
    
    async def execute(self, connection_id: Optional[str] = None) -> Dict[str, Any]:
        """Execute the tool.
        
        Args:
            connection_id: Optional ID of the connection to disconnect from.
                          If not provided, disconnects from all connections.
        """
        try:
            manager = get_connection_manager()
            
            if connection_id:
                conn = manager.get_connection(connection_id)
                if not conn:
                    return {
                        "success": False,
                        "error": f"Connection not found: {connection_id}"
                    }
                
                await conn.disconnect()
                return {
                    "success": True,
                    "connection_id": connection_id,
                    "message": "Disconnected successfully"
                }
            else:
                await manager.disconnect_all()
                return {
                    "success": True,
                    "message": "Disconnected from all ClawSocial instances"
                }
            
        except Exception as e:
            logger.error(f"Failed to disconnect ClawSocial: {e}")
            return {
                "success": False,
                "error": str(e)
            }
