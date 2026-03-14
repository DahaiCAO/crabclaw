"""Internal tools for Crabclaw agent."""

from typing import Any, Dict

from crabclaw.agent.tools.base import Tool
from loguru import logger


class ReloadSkillsTool(Tool):
    """Tool for reloading skills."""
    
    def __init__(self, skill_manager):
        self.skill_manager = skill_manager
    
    @property
    def name(self) -> str:
        return "reload_skills"
    
    @property
    def description(self) -> str:
        return "Reload all skills from the workspace"
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
    
    async def execute(self, **kwargs) -> str:
        """Execute the tool."""
        try:
            # Get the tool registry from the parent agent
            from crabclaw.agent.loop import AgentLoop
            for obj in globals().values():
                if isinstance(obj, AgentLoop):
                    tool_registry = obj.tools
                    break
            else:
                return "Error: Could not access tool registry"
            
            # Refresh all skills
            refreshed_skills = await self.skill_manager.refresh_skills(tool_registry)
            return f"Successfully reloaded {len(refreshed_skills)} skills: {', '.join(refreshed_skills)}"
        except Exception as e:
            logger.error(f"Error reloading skills: {e}")
            return f"Error reloading skills: {str(e)}"


class SearchSkillsTool(Tool):
    """Tool for searching skills in repositories."""
    
    def __init__(self, skill_manager):
        self.skill_manager = skill_manager
    
    @property
    def name(self) -> str:
        return "search_skills"
    
    @property
    def description(self) -> str:
        return "Search for skills in online repositories"
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query for skills"
                }
            },
            "required": []
        }
    
    async def execute(self, query: str = "", **kwargs) -> str:
        """Execute the tool."""
        try:
            # Search for skills
            results = await self.skill_manager.search_skills(query)
            if results:
                response = f"Found {len(results)} skills:\n"
                for skill in results:
                    response += f"- {skill['name']}: {skill['description']} (from {skill['repository']})\n"
                return response
            else:
                return "No skills found."
        except Exception as e:
            logger.error(f"Error searching skills: {e}")
            return f"Error searching skills: {str(e)}"


class DownloadSkillTool(Tool):
    """Tool for downloading skills from repositories."""
    
    def __init__(self, skill_manager):
        self.skill_manager = skill_manager
    
    @property
    def name(self) -> str:
        return "download_skill"
    
    @property
    def description(self) -> str:
        return "Download a skill from an online repository"
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "skill_id": {
                    "type": "string",
                    "description": "ID of the skill to download"
                },
                "repository_url": {
                    "type": "string",
                    "description": "URL of the repository to download from"
                }
            },
            "required": ["skill_id", "repository_url"]
        }
    
    async def execute(self, skill_id: str, repository_url: str, **kwargs) -> str:
        """Execute the tool."""
        try:
            # Get the tool registry from the parent agent
            from crabclaw.agent.loop import AgentLoop
            for obj in globals().values():
                if isinstance(obj, AgentLoop):
                    tool_registry = obj.tools
                    break
            else:
                return "Error: Could not access tool registry"
            
            # Download the skill
            success = await self.skill_manager.download_skill(skill_id, repository_url)
            if success:
                # Hot load the skill
                hot_load_success = await self.skill_manager.hot_load_skill(skill_id, tool_registry)
                if hot_load_success:
                    return f"Successfully downloaded and loaded skill {skill_id}"
                else:
                    return f"Successfully downloaded skill {skill_id}, but failed to load it"
            else:
                return f"Failed to download skill {skill_id}"
        except Exception as e:
            logger.error(f"Error downloading skill: {e}")
            return f"Error downloading skill: {str(e)}"
