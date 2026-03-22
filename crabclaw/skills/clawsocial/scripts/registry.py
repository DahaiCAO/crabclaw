"""Registry tool for ClawSocial."""
import json
from typing import Any

import requests

from .base import ClawSocialBaseTool
from .config import config


class RegistryTool(ClawSocialBaseTool):
    """Tool for Crabclaw registration."""
    
    @property
    def name(self) -> str:
        return "clawsocial_register"
    
    @property
    def description(self) -> str:
        return "Register a Crabclaw agent with ClawSocialGraph"
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "display_name": {
                    "type": "string",
                    "description": "Display name for agent (optional)"
                },
                "endpoint_host": {
                    "type": "string",
                    "description": "Hostname where the agent is running (optional)"
                },
                "endpoint_port": {
                    "type": "integer",
                    "description": "Port where the agent is listening (optional)"
                }
            }
        }
    
    async def execute(self, **kwargs) -> str:
        """Execute registration."""
        # Get agent ID from config or generate one
        from crabclaw.config.loader import load_config
        from .config import config as clawsocial_config
        
        crabclaw_config = load_config()
        agent_id = crabclaw_config.agent_id
        
        # Check if already registered
        try:
            check_url = clawsocial_config.router_url.rstrip("/") + f"/social/crabclaw/{agent_id}"
            response = requests.get(check_url, timeout=clawsocial_config.timeout_sec)
            if response.status_code == 200:
                # If registered but name changed locally, we might want to update it
                # We'll implement a separate update_profile tool for that
                return f"Already registered! Agent ID: {agent_id}"
        except requests.RequestException:
            # If check fails, proceed with registration
            pass
        
        # Determine display name:
        # 1. Parameter provided by user/agent
        # 2. Configured agent_name
        # 3. Default "Agent_{id}"
        default_name = crabclaw_config.agent_name or f"Agent_{agent_id}"
        display_name = kwargs.get("display_name", default_name)
        endpoint_host = kwargs.get("endpoint_host", "localhost")
        endpoint_port = kwargs.get("endpoint_port", 8080)
        capabilities = kwargs.get("capabilities", ["chat", "web_search", "file_operations", "scheduling", "code_execution"])
        public_key = kwargs.get("public_key")
        metadata = kwargs.get("metadata", {})
        
        if not all([agent_id, display_name, endpoint_host, endpoint_port]):
            return "Error: Missing required parameters"
        
        payload = {
            "agent_id": agent_id,
            "display_name": display_name,
            "endpoint_host": endpoint_host,
            "endpoint_port": endpoint_port,
            "capabilities": capabilities,
            "metadata": metadata
        }
        
        if public_key:
            payload["public_key"] = public_key
        
        url = clawsocial_config.router_url.rstrip("/") + "/social/crabclaw/register"
        
        try:
            response = requests.post(url, json=payload, timeout=clawsocial_config.timeout_sec)
            response.raise_for_status()
            return json.dumps(response.json(), ensure_ascii=False, indent=2)
        except requests.RequestException as exc:
            return f"Error: {str(exc)}"


class ProfileUpdateTool(ClawSocialBaseTool):
    """Tool for updating Crabclaw profile."""
    
    @property
    def name(self) -> str:
        return "clawsocial_profile_update"
    
    @property
    def description(self) -> str:
        return "Update my Crabclaw profile (display name, etc.) and save locally"
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "display_name": {
                    "type": "string",
                    "description": "New display name"
                },
                "endpoint_host": {
                    "type": "string",
                    "description": "New endpoint host"
                },
                "endpoint_port": {
                    "type": "integer",
                    "description": "New endpoint port"
                }
            }
        }
    
    async def execute(self, **kwargs) -> str:
        """Execute profile update."""
        from crabclaw.config.loader import load_config, save_config
        from .config import config as clawsocial_config
        
        crabclaw_config = load_config()
        agent_id = crabclaw_config.agent_id
        
        updates = {}
        if "display_name" in kwargs:
            updates["display_name"] = kwargs["display_name"]
            # Save locally
            crabclaw_config.agent_name = kwargs["display_name"]
            save_config(crabclaw_config)
            
        if "endpoint_host" in kwargs:
            updates["endpoint_host"] = kwargs["endpoint_host"]
        if "endpoint_port" in kwargs:
            updates["endpoint_port"] = kwargs["endpoint_port"]
            
        if not updates:
            return "Error: No valid fields to update provided."
            
        url = clawsocial_config.router_url.rstrip("/") + f"/social/crabclaw/{agent_id}/update"
        
        try:
            response = requests.post(url, json=updates, timeout=clawsocial_config.timeout_sec)
            response.raise_for_status()
            return f"Successfully updated profile.\nNew Profile: {json.dumps(response.json().get('profile', {}), ensure_ascii=False, indent=2)}"
        except requests.RequestException as exc:
            return f"Error updating remote profile (local config was updated if display_name was provided): {str(exc)}"


class RegistryListTool(ClawSocialBaseTool):
    """Tool for listing all registered Crabclaw agents."""
    
    @property
    def name(self) -> str:
        return "clawsocial_register_list"
    
    @property
    def description(self) -> str:
        return "List all registered Crabclaw agents in ClawSocialGraph"
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {}
        }
    
    async def execute(self, **kwargs) -> str:
        """Execute list registered agents."""
        url = config.router_url.rstrip("/") + "/social/crabclaw"
        
        try:
            response = requests.get(url, timeout=config.timeout_sec)
            response.raise_for_status()
            return json.dumps(response.json(), ensure_ascii=False, indent=2)
        except requests.RequestException as exc:
            return f"Error: {str(exc)}"
