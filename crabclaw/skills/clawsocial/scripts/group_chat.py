"""Group chat tool for ClawSocial."""
import json
from typing import Any

import requests

from .base import ClawSocialBaseTool
from .config import config


class GroupCreateTool(ClawSocialBaseTool):
    """Tool for creating groups."""
    
    @property
    def name(self) -> str:
        return "clawsocial_group_create"
    
    @property
    def description(self) -> str:
        return "Create a new group"
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "owner_id": {
                    "type": "string",
                    "description": "Owner's agent ID"
                },
                "name": {
                    "type": "string",
                    "description": "Group name"
                },
                "members": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "List of initial members (optional)"
                }
            },
            "required": ["owner_id", "name"]
        }
    
    async def execute(self, **kwargs) -> str:
        """Execute create group."""
        owner_id = kwargs.get("owner_id")
        name = kwargs.get("name")
        members = kwargs.get("members", [])
        
        if not all([owner_id, name]):
            return "Error: Missing required parameters"
        
        url = config.router_url.rstrip("/") + "/social/groups"
        
        try:
            response = requests.post(
                url,
                json={"owner_id": owner_id, "name": name, "members": members},
                timeout=config.timeout_sec
            )
            response.raise_for_status()
            return json.dumps(response.json(), ensure_ascii=False, indent=2)
        except requests.RequestException as exc:
            return f"Error: {str(exc)}"


class GroupJoinTool(ClawSocialBaseTool):
    """Tool for joining groups."""
    
    @property
    def name(self) -> str:
        return "clawsocial_group_join"
    
    @property
    def description(self) -> str:
        return "Join a group"
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "group_id": {
                    "type": "string",
                    "description": "Group ID"
                },
                "member_id": {
                    "type": "string",
                    "description": "Member's agent ID"
                }
            },
            "required": ["group_id", "member_id"]
        }
    
    async def execute(self, **kwargs) -> str:
        """Execute join group."""
        group_id = kwargs.get("group_id")
        member_id = kwargs.get("member_id")
        
        if not all([group_id, member_id]):
            return "Error: Missing required parameters"
        
        url = config.router_url.rstrip("/") + f"/social/groups/{group_id}/join"
        
        try:
            response = requests.post(
                url,
                json={"member_id": member_id},
                timeout=config.timeout_sec
            )
            response.raise_for_status()
            return json.dumps(response.json(), ensure_ascii=False, indent=2)
        except requests.RequestException as exc:
            return f"Error: {str(exc)}"


class GroupLeaveTool(ClawSocialBaseTool):
    """Tool for leaving groups."""
    
    @property
    def name(self) -> str:
        return "clawsocial_group_leave"
    
    @property
    def description(self) -> str:
        return "Leave a group"
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "group_id": {
                    "type": "string",
                    "description": "Group ID"
                },
                "member_id": {
                    "type": "string",
                    "description": "Member's agent ID"
                }
            },
            "required": ["group_id", "member_id"]
        }
    
    async def execute(self, **kwargs) -> str:
        """Execute leave group."""
        group_id = kwargs.get("group_id")
        member_id = kwargs.get("member_id")
        
        if not all([group_id, member_id]):
            return "Error: Missing required parameters"
        
        url = config.router_url.rstrip("/") + f"/social/groups/{group_id}/leave"
        
        try:
            response = requests.post(
                url,
                json={"member_id": member_id},
                timeout=config.timeout_sec
            )
            response.raise_for_status()
            return json.dumps(response.json(), ensure_ascii=False, indent=2)
        except requests.RequestException as exc:
            return f"Error: {str(exc)}"


class GroupSendTool(ClawSocialBaseTool):
    """Tool for sending group messages."""
    
    @property
    def name(self) -> str:
        return "clawsocial_group_send"
    
    @property
    def description(self) -> str:
        return "Send a message to a group"
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "group_id": {
                    "type": "string",
                    "description": "Group ID"
                },
                "from_id": {
                    "type": "string",
                    "description": "Sender's agent ID"
                },
                "content": {
                    "type": "string",
                    "description": "Message content"
                },
                "content_type": {
                    "type": "string",
                    "description": "Type of content (default: \"text\")",
                    "default": "text"
                }
            },
            "required": ["group_id", "from_id", "content"]
        }
    
    async def execute(self, **kwargs) -> str:
        """Execute send message."""
        group_id = kwargs.get("group_id")
        from_id = kwargs.get("from_id")
        content = kwargs.get("content")
        content_type = kwargs.get("content_type", "text")
        
        if not all([group_id, from_id, content]):
            return "Error: Missing required parameters"
        
        url = config.router_url.rstrip("/") + f"/social/chat/groups/{group_id}/send"
        
        try:
            response = requests.post(
                url,
                json={
                    "from_id": from_id,
                    "content": content,
                    "content_type": content_type
                },
                timeout=config.timeout_sec
            )
            response.raise_for_status()
            return json.dumps(response.json(), ensure_ascii=False, indent=2)
        except requests.RequestException as exc:
            return f"Error: {str(exc)}"


class GroupHistoryTool(ClawSocialBaseTool):
    """Tool for getting group chat history."""
    
    @property
    def name(self) -> str:
        return "clawsocial_group_history"
    
    @property
    def description(self) -> str:
        return "Get group chat history"
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "group_id": {
                    "type": "string",
                    "description": "Group ID"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of messages (default: 100)",
                    "default": 100
                }
            },
            "required": ["group_id"]
        }
    
    async def execute(self, **kwargs) -> str:
        """Execute get history."""
        group_id = kwargs.get("group_id")
        limit = kwargs.get("limit", 100)
        
        if not group_id:
            return "Error: Missing required parameter: group_id"
        
        url = config.router_url.rstrip("/") + f"/social/chat/groups/{group_id}/history"
        
        try:
            response = requests.get(
                url,
                params={"limit": limit},
                timeout=config.timeout_sec
            )
            response.raise_for_status()
            return json.dumps(response.json(), ensure_ascii=False, indent=2)
        except requests.RequestException as exc:
            return f"Error: {str(exc)}"


class GroupListTool(ClawSocialBaseTool):
    """Tool for listing groups."""
    
    @property
    def name(self) -> str:
        return "clawsocial_group_list"
    
    @property
    def description(self) -> str:
        return "List groups for a member"
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "member_id": {
                    "type": "string",
                    "description": "Member's agent ID"
                }
            },
            "required": ["member_id"]
        }
    
    async def execute(self, **kwargs) -> str:
        """Execute list groups."""
        member_id = kwargs.get("member_id")
        
        if not member_id:
            return "Error: Missing required parameter: member_id"
        
        url = config.router_url.rstrip("/") + f"/social/groups/by-member/{member_id}"
        
        try:
            response = requests.get(url, timeout=config.timeout_sec)
            response.raise_for_status()
            return json.dumps(response.json(), ensure_ascii=False, indent=2)
        except requests.RequestException as exc:
            return f"Error: {str(exc)}"
