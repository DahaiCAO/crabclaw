"""Registry tool for ClawSocial."""
import json
from typing import Any

import httpx

from .base import ClawSocialBaseTool
from .config import config


class RegistryTool(ClawSocialBaseTool):
    """Tool for OpenClaw registration."""
    
    @property
    def name(self) -> str:
        return "clawsocial_register"
    
    @property
    def description(self) -> str:
        return "Register an OpenClaw agent with ClawSocialGraph"
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "openclaw_id": {
                    "type": "string",
                    "description": "Unique ID for the agent"
                },
                "display_name": {
                    "type": "string",
                    "description": "Display name for the agent"
                },
                "endpoint_host": {
                    "type": "string",
                    "description": "Hostname where the agent is running"
                },
                "endpoint_port": {
                    "type": "integer",
                    "description": "Port where the agent is listening"
                },
                "capabilities": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "List of capabilities (optional)"
                },
                "public_key": {
                    "type": "string",
                    "description": "Public key for secure communication (optional)"
                },
                "metadata": {
                    "type": "object",
                    "description": "Additional metadata (optional)"
                }
            },
            "required": ["openclaw_id", "display_name", "endpoint_host", "endpoint_port"]
        }
    
    async def execute(self, **kwargs) -> str:
        """Execute registration."""
        openclaw_id = kwargs.get("openclaw_id")
        display_name = kwargs.get("display_name")
        endpoint_host = kwargs.get("endpoint_host")
        endpoint_port = kwargs.get("endpoint_port")
        capabilities = kwargs.get("capabilities", [])
        public_key = kwargs.get("public_key")
        metadata = kwargs.get("metadata", {})
        
        if not all([openclaw_id, display_name, endpoint_host, endpoint_port]):
            return "Error: Missing required parameters"
        
        payload = {
            "openclaw_id": openclaw_id,
            "display_name": display_name,
            "endpoint_host": endpoint_host,
            "endpoint_port": endpoint_port,
            "capabilities": capabilities,
            "metadata": metadata
        }
        
        if public_key:
            payload["public_key"] = public_key
        
        url = config.router_url.rstrip("/") + "/social/openclaw/register"
        
        try:
            response = httpx.post(url, json=payload, timeout=config.timeout_sec)
            response.raise_for_status()
            return json.dumps(response.json(), ensure_ascii=False, indent=2)
        except httpx.HTTPError as exc:
            return f"Error: {str(exc)}"
