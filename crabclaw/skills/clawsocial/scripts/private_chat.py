"""Private chat tool for ClawSocial."""
import json
from typing import Any

import httpx

from .base import ClawSocialBaseTool
from .config import config


class PrivateChatSendTool(ClawSocialBaseTool):
    """Tool for sending private messages."""
    
    @property
    def name(self) -> str:
        return "clawsocial_private_chat_send"
    
    @property
    def description(self) -> str:
        return "Send a private message to another agent"
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "from_id": {
                    "type": "string",
                    "description": "Sender's agent ID"
                },
                "to_id": {
                    "type": "string",
                    "description": "Recipient's agent ID"
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
            "required": ["from_id", "to_id", "content"]
        }
    
    async def execute(self, **kwargs) -> str:
        """Execute send message."""
        from_id = kwargs.get("from_id")
        to_id = kwargs.get("to_id")
        content = kwargs.get("content")
        content_type = kwargs.get("content_type", "text")
        
        if not all([from_id, to_id, content]):
            return "Error: Missing required parameters"
        
        url = config.router_url.rstrip("/") + "/social/chat/private/send"
        
        try:
            response = httpx.post(
                url,
                json={
                    "from_id": from_id,
                    "to_id": to_id,
                    "content": content,
                    "content_type": content_type
                },
                timeout=config.timeout_sec
            )
            response.raise_for_status()
            return json.dumps(response.json(), ensure_ascii=False, indent=2)
        except httpx.HTTPError as exc:
            return f"Error: {str(exc)}"


class PrivateChatHistoryTool(ClawSocialBaseTool):
    """Tool for getting private chat history."""
    
    @property
    def name(self) -> str:
        return "clawsocial_private_chat_history"
    
    @property
    def description(self) -> str:
        return "Get private chat history between two agents"
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "left_id": {
                    "type": "string",
                    "description": "First agent ID"
                },
                "right_id": {
                    "type": "string",
                    "description": "Second agent ID"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of messages (default: 50)",
                    "default": 50
                }
            },
            "required": ["left_id", "right_id"]
        }
    
    async def execute(self, **kwargs) -> str:
        """Execute get history."""
        left_id = kwargs.get("left_id")
        right_id = kwargs.get("right_id")
        limit = kwargs.get("limit", 50)
        
        if not all([left_id, right_id]):
            return "Error: Missing required parameters"
        
        url = config.router_url.rstrip("/") + "/social/chat/private/history"
        
        try:
            response = httpx.get(
                url,
                params={
                    "left_id": left_id,
                    "right_id": right_id,
                    "limit": limit
                },
                timeout=config.timeout_sec
            )
            response.raise_for_status()
            return json.dumps(response.json(), ensure_ascii=False, indent=2)
        except httpx.HTTPError as exc:
            return f"Error: {str(exc)}"
