"""Contacts tool for ClawSocial."""
import json
from typing import Any

import requests

from .base import ClawSocialBaseTool
from .config import config


class ContactsAddTool(ClawSocialBaseTool):
    """Tool for adding contacts."""
    
    @property
    def name(self) -> str:
        return "clawsocial_contacts_add"
    
    @property
    def description(self) -> str:
        return "Add a contact"
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "owner_id": {
                    "type": "string",
                    "description": "Owner's agent ID"
                },
                "target_id": {
                    "type": "string",
                    "description": "Target agent ID to add as contact"
                }
            },
            "required": ["owner_id", "target_id"]
        }
    
    async def execute(self, **kwargs) -> str:
        """Execute add contact."""
        owner_id = kwargs.get("owner_id")
        target_id = kwargs.get("target_id")
        
        if not all([owner_id, target_id]):
            return "Error: Missing required parameters"
        
        url = config.router_url.rstrip("/") + "/social/contacts/add"
        
        try:
            response = requests.post(
                url,
                json={"owner_id": owner_id, "target_id": target_id},
                timeout=config.timeout_sec
            )
            response.raise_for_status()
            return json.dumps(response.json(), ensure_ascii=False, indent=2)
        except requests.RequestException as exc:
            return f"Error: {str(exc)}"


class ContactsRemoveTool(ClawSocialBaseTool):
    """Tool for removing contacts."""
    
    @property
    def name(self) -> str:
        return "clawsocial_contacts_remove"
    
    @property
    def description(self) -> str:
        return "Remove a contact"
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "owner_id": {
                    "type": "string",
                    "description": "Owner's agent ID"
                },
                "target_id": {
                    "type": "string",
                    "description": "Target agent ID to remove from contacts"
                }
            },
            "required": ["owner_id", "target_id"]
        }
    
    async def execute(self, **kwargs) -> str:
        """Execute remove contact."""
        owner_id = kwargs.get("owner_id")
        target_id = kwargs.get("target_id")
        
        if not all([owner_id, target_id]):
            return "Error: Missing required parameters"
        
        url = config.router_url.rstrip("/") + "/social/contacts/remove"
        
        try:
            response = requests.post(
                url,
                json={"owner_id": owner_id, "target_id": target_id},
                timeout=config.timeout_sec
            )
            response.raise_for_status()
            return json.dumps(response.json(), ensure_ascii=False, indent=2)
        except requests.RequestException as exc:
            return f"Error: {str(exc)}"


class ContactsListTool(ClawSocialBaseTool):
    """Tool for listing contacts."""
    
    @property
    def name(self) -> str:
        return "clawsocial_contacts_list"
    
    @property
    def description(self) -> str:
        return "List contacts for an owner"
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "owner_id": {
                    "type": "string",
                    "description": "Owner's agent ID"
                }
            },
            "required": ["owner_id"]
        }
    
    async def execute(self, **kwargs) -> str:
        """Execute list contacts."""
        owner_id = kwargs.get("owner_id")
        
        if not owner_id:
            return "Error: Missing required parameter: owner_id"
        
        url = config.router_url.rstrip("/") + f"/social/contacts/{owner_id}"
        
        try:
            response = requests.get(url, timeout=config.timeout_sec)
            response.raise_for_status()
            return json.dumps(response.json(), ensure_ascii=False, indent=2)
        except requests.RequestException as exc:
            return f"Error: {str(exc)}"
