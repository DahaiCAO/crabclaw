"""Group admin tool for ClawSocial."""
import json
from typing import Any

import httpx

from .base import ClawSocialBaseTool
from .config import config


class GroupGrantAdminTool(ClawSocialBaseTool):
    """Tool for granting admin privileges."""
    
    @property
    def name(self) -> str:
        return "clawsocial_group_grant_admin"
    
    @property
    def description(self) -> str:
        return "Grant admin privileges to a group member"
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "group_id": {
                    "type": "string",
                    "description": "Group ID"
                },
                "actor_id": {
                    "type": "string",
                    "description": "Actor's agent ID (must be an admin)"
                },
                "member_id": {
                    "type": "string",
                    "description": "Member's agent ID to grant admin privileges"
                }
            },
            "required": ["group_id", "actor_id", "member_id"]
        }
    
    async def execute(self, **kwargs) -> str:
        """Execute grant admin."""
        group_id = kwargs.get("group_id")
        actor_id = kwargs.get("actor_id")
        member_id = kwargs.get("member_id")
        
        if not all([group_id, actor_id, member_id]):
            return "Error: Missing required parameters"
        
        url = config.router_url.rstrip("/") + f"/social/groups/{group_id}/admins/grant"
        
        try:
            response = httpx.post(
                url,
                json={"actor_id": actor_id, "member_id": member_id},
                timeout=config.timeout_sec
            )
            response.raise_for_status()
            return json.dumps(response.json(), ensure_ascii=False, indent=2)
        except httpx.HTTPError as exc:
            return f"Error: {str(exc)}"


class GroupRevokeAdminTool(ClawSocialBaseTool):
    """Tool for revoking admin privileges."""
    
    @property
    def name(self) -> str:
        return "clawsocial_group_revoke_admin"
    
    @property
    def description(self) -> str:
        return "Revoke admin privileges from a group member"
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "group_id": {
                    "type": "string",
                    "description": "Group ID"
                },
                "actor_id": {
                    "type": "string",
                    "description": "Actor's agent ID (must be an admin)"
                },
                "member_id": {
                    "type": "string",
                    "description": "Member's agent ID to revoke admin privileges"
                }
            },
            "required": ["group_id", "actor_id", "member_id"]
        }
    
    async def execute(self, **kwargs) -> str:
        """Execute revoke admin."""
        group_id = kwargs.get("group_id")
        actor_id = kwargs.get("actor_id")
        member_id = kwargs.get("member_id")
        
        if not all([group_id, actor_id, member_id]):
            return "Error: Missing required parameters"
        
        url = config.router_url.rstrip("/") + f"/social/groups/{group_id}/admins/revoke"
        
        try:
            response = httpx.post(
                url,
                json={"actor_id": actor_id, "member_id": member_id},
                timeout=config.timeout_sec
            )
            response.raise_for_status()
            return json.dumps(response.json(), ensure_ascii=False, indent=2)
        except httpx.HTTPError as exc:
            return f"Error: {str(exc)}"


class GroupRemoveMemberTool(ClawSocialBaseTool):
    """Tool for removing group members."""
    
    @property
    def name(self) -> str:
        return "clawsocial_group_remove_member"
    
    @property
    def description(self) -> str:
        return "Remove a member from a group"
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "group_id": {
                    "type": "string",
                    "description": "Group ID"
                },
                "actor_id": {
                    "type": "string",
                    "description": "Actor's agent ID (must be an admin)"
                },
                "member_id": {
                    "type": "string",
                    "description": "Member's agent ID to remove"
                }
            },
            "required": ["group_id", "actor_id", "member_id"]
        }
    
    async def execute(self, **kwargs) -> str:
        """Execute remove member."""
        group_id = kwargs.get("group_id")
        actor_id = kwargs.get("actor_id")
        member_id = kwargs.get("member_id")
        
        if not all([group_id, actor_id, member_id]):
            return "Error: Missing required parameters"
        
        url = config.router_url.rstrip("/") + f"/social/groups/{group_id}/members/remove"
        
        try:
            response = httpx.post(
                url,
                json={"actor_id": actor_id, "member_id": member_id},
                timeout=config.timeout_sec
            )
            response.raise_for_status()
            return json.dumps(response.json(), ensure_ascii=False, indent=2)
        except httpx.HTTPError as exc:
            return f"Error: {str(exc)}"


class GroupSetAnnouncementTool(ClawSocialBaseTool):
    """Tool for setting group announcements."""
    
    @property
    def name(self) -> str:
        return "clawsocial_group_set_announcement"
    
    @property
    def description(self) -> str:
        return "Set group announcement"
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "group_id": {
                    "type": "string",
                    "description": "Group ID"
                },
                "actor_id": {
                    "type": "string",
                    "description": "Actor's agent ID (must be an admin)"
                },
                "announcement": {
                    "type": "string",
                    "description": "Announcement content"
                }
            },
            "required": ["group_id", "actor_id", "announcement"]
        }
    
    async def execute(self, **kwargs) -> str:
        """Execute set announcement."""
        group_id = kwargs.get("group_id")
        actor_id = kwargs.get("actor_id")
        announcement = kwargs.get("announcement")
        
        if not all([group_id, actor_id, announcement]):
            return "Error: Missing required parameters"
        
        url = config.router_url.rstrip("/") + f"/social/groups/{group_id}/announcement"
        
        try:
            response = httpx.post(
                url,
                json={"actor_id": actor_id, "announcement": announcement},
                timeout=config.timeout_sec
            )
            response.raise_for_status()
            return json.dumps(response.json(), ensure_ascii=False, indent=2)
        except httpx.HTTPError as exc:
            return f"Error: {str(exc)}"


class GroupMembersTool(ClawSocialBaseTool):
    """Tool for listing group members."""
    
    @property
    def name(self) -> str:
        return "clawsocial_group_members"
    
    @property
    def description(self) -> str:
        return "List group members"
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "group_id": {
                    "type": "string",
                    "description": "Group ID"
                }
            },
            "required": ["group_id"]
        }
    
    async def execute(self, **kwargs) -> str:
        """Execute list members."""
        group_id = kwargs.get("group_id")
        
        if not group_id:
            return "Error: Missing required parameter: group_id"
        
        url = config.router_url.rstrip("/") + f"/social/groups/{group_id}/members"
        
        try:
            response = httpx.get(url, timeout=config.timeout_sec)
            response.raise_for_status()
            return json.dumps(response.json(), ensure_ascii=False, indent=2)
        except httpx.HTTPError as exc:
            return f"Error: {str(exc)}"
