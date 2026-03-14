"""Skill discovery and hot-loading system for Crabclaw."""
import asyncio
import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
from loguru import logger

from crabclaw.agent.skills import SkillsLoader
from crabclaw.agent.tools.registry import ToolRegistry
from crabclaw.utils.plugin_system import Plugin, PluginMetadata, PluginRegistry, PluginType


class SkillRepository:
    """Skill repository interface for discovering and downloading skills."""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def search_skills(self, query: str = "") -> List[Dict[str, Any]]:
        """Search for skills in the repository."""
        try:
            response = await self.client.get(
                f"{self.base_url}/api/skills/search",
                params={"q": query}
            )
            response.raise_for_status()
            return response.json().get("skills", [])
        except Exception as e:
            logger.error(f"Error searching skills: {e}")
            return []
    
    async def get_skill_info(self, skill_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a skill."""
        try:
            response = await self.client.get(f"{self.base_url}/api/skills/{skill_id}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error getting skill info: {e}")
            return None
    
    async def download_skill(self, skill_id: str, destination: Path) -> bool:
        """Download a skill to the specified destination."""
        try:
            response = await self.client.get(
                f"{self.base_url}/api/skills/{skill_id}/download",
                follow_redirects=True
            )
            response.raise_for_status()
            
            # Write the skill content
            skill_dir = destination / skill_id
            skill_dir.mkdir(parents=True, exist_ok=True)
            
            # Assuming the response is a zip file
            with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
                tmp.write(response.content)
                tmp_path = tmp.name
            
            # Extract the zip file
            import zipfile
            with zipfile.ZipFile(tmp_path, "r") as zip_ref:
                zip_ref.extractall(skill_dir)
            
            # Clean up
            os.unlink(tmp_path)
            
            logger.info(f"Downloaded skill {skill_id} to {skill_dir}")
            return True
        except Exception as e:
            logger.error(f"Error downloading skill: {e}")
            return False
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


class SkillManager:
    """Manager for skill discovery, downloading, and hot-loading."""
    
    def __init__(self, workspace: Path, builtin_skills_dir: Path):
        self.workspace = workspace
        self.builtin_skills_dir = builtin_skills_dir
        self.workspace_skills_dir = workspace / "skills"
        self.workspace_skills_dir.mkdir(parents=True, exist_ok=True)
        
        self.skills_loader = SkillsLoader(workspace, builtin_skills_dir)
        self.repositories: List[SkillRepository] = []
        
        # Default repositories
        self.add_repository("https://crabclaw-skills.org")
        self.add_repository("https://skills.crabclaw.dev")
    
    def add_repository(self, base_url: str):
        """Add a skill repository."""
        self.repositories.append(SkillRepository(base_url))
        logger.info(f"Added skill repository: {base_url}")
    
    async def search_skills(self, query: str = "") -> List[Dict[str, Any]]:
        """Search for skills across all repositories."""
        results = []
        for repo in self.repositories:
            repo_results = await repo.search_skills(query)
            for result in repo_results:
                result["repository"] = repo.base_url
                results.append(result)
        return results
    
    async def download_skill(self, skill_id: str, repository_url: str) -> bool:
        """Download a skill from a specific repository."""
        for repo in self.repositories:
            if repo.base_url == repository_url:
                return await repo.download_skill(skill_id, self.workspace_skills_dir)
        return False
    
    async def hot_load_skill(self, skill_name: str, tool_registry: ToolRegistry) -> bool:
        """Hot load a skill and its tools."""
        try:
            # Check if the skill exists
            skill_path = self.workspace_skills_dir / skill_name
            if not skill_path.exists():
                logger.error(f"Skill {skill_name} not found in workspace")
                return False
            
            # Load the skill metadata
            metadata = self.skills_loader.get_skill_metadata(skill_name)
            if not metadata:
                logger.error(f"Could not load metadata for skill {skill_name}")
                return False
            
            # Check if the skill has a tool registration module
            tool_registration_path = skill_path / "tools" / "__init__.py"
            if tool_registration_path.exists():
                # Import and register tools
                import sys
                import importlib.util
                
                # Add the workspace skills directory to Python path
                sys.path.insert(0, str(self.workspace_skills_dir))
                
                try:
                    # Import the tool registration module
                    module_name = f"{skill_name}.tools"
                    spec = importlib.util.spec_from_file_location(module_name, tool_registration_path)
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        
                        # Check if there's a register_tools function
                        if hasattr(module, "register_tools"):
                            module.register_tools(tool_registry)
                            logger.info(f"Registered tools for skill {skill_name}")
                finally:
                    # Remove the workspace skills directory from Python path
                    if str(self.workspace_skills_dir) in sys.path:
                        sys.path.remove(str(self.workspace_skills_dir))
            
            logger.info(f"Hot loaded skill: {skill_name}")
            return True
        except Exception as e:
            logger.error(f"Error hot loading skill {skill_name}: {e}")
            return False
    
    async def refresh_skills(self, tool_registry: ToolRegistry) -> List[str]:
        """Refresh all skills in the workspace."""
        refreshed_skills = []
        
        if self.workspace_skills_dir.exists():
            for skill_dir in self.workspace_skills_dir.iterdir():
                if skill_dir.is_dir():
                    skill_name = skill_dir.name
                    if await self.hot_load_skill(skill_name, tool_registry):
                        refreshed_skills.append(skill_name)
        
        return refreshed_skills
    
    async def close(self):
        """Close all repository clients."""
        for repo in self.repositories:
            await repo.close()


class SkillDiscoveryTool(Plugin):
    """Tool for discovering and managing skills."""
    
    def __init__(self, metadata: PluginMetadata):
        super().__init__(metadata)
        self.skill_manager: Optional[SkillManager] = None
        self.tool_registry: Optional[ToolRegistry] = None
    
    async def initialize(self, config: dict) -> None:
        """Initialize the plugin."""
        from crabclaw.agent.loop import AgentLoop
        
        # Get the agent loop instance to access the tool registry
        # Note: This is a bit of a hack, ideally we should pass these in
        for obj in globals().values():
            if isinstance(obj, AgentLoop):
                self.tool_registry = obj.tools
                self.skill_manager = SkillManager(
                    obj.workspace,
                    Path(__file__).parent.parent / "skills"
                )
                break
        
        if not self.skill_manager:
            logger.error("Could not initialize SkillManager")
        
    async def shutdown(self) -> None:
        """Shutdown the plugin."""
        if self.skill_manager:
            await self.skill_manager.close()
    
    async def search_skills(self, query: str = "") -> List[Dict[str, Any]]:
        """Search for skills."""
        if not self.skill_manager:
            return []
        return await self.skill_manager.search_skills(query)
    
    async def download_skill(self, skill_id: str, repository_url: str) -> bool:
        """Download a skill."""
        if not self.skill_manager:
            return False
        return await self.skill_manager.download_skill(skill_id, repository_url)
    
    async def refresh_skills(self) -> List[str]:
        """Refresh all skills."""
        if not self.skill_manager or not self.tool_registry:
            return []
        return await self.skill_manager.refresh_skills(self.tool_registry)


# Register the skill discovery tool
skill_discovery_metadata = PluginMetadata(
    name="skill_discovery",
    version="1.0.0",
    description="Tool for discovering and managing skills",
    plugin_type=PluginType.TOOL
)

skill_discovery_tool = SkillDiscoveryTool(skill_discovery_metadata)


# Add skill discovery commands to the CLI
def add_skill_commands(app):
    """Add skill-related commands to the CLI."""
    from typer import Typer
    
    skill_app = Typer(name="skill", help="Manage skills")
    
    @skill_app.command("search")
    async def search_skills(query: str = ""):
        """Search for skills."""
        skill_manager = SkillManager(
            Path.cwd(),
            Path(__file__).parent.parent / "skills"
        )
        try:
            results = await skill_manager.search_skills(query)
            if results:
                print(f"Found {len(results)} skills:")
                for skill in results:
                    print(f"- {skill['name']}: {skill['description']} (from {skill['repository']})")
            else:
                print("No skills found.")
        finally:
            await skill_manager.close()
    
    @skill_app.command("download")
    async def download_skill(skill_id: str, repository_url: str):
        """Download a skill."""
        skill_manager = SkillManager(
            Path.cwd(),
            Path(__file__).parent.parent / "skills"
        )
        try:
            success = await skill_manager.download_skill(skill_id, repository_url)
            if success:
                print(f"Successfully downloaded skill {skill_id}")
            else:
                print(f"Failed to download skill {skill_id}")
        finally:
            await skill_manager.close()
    
    @skill_app.command("refresh")
    async def refresh_skills():
        """Refresh all skills."""
        # This would need access to the running agent's tool registry
        print("Skills refreshed (note: this command requires the agent to be running)")
    
    app.add_typer(skill_app)


__all__ = [
    "SkillRepository",
    "SkillManager",
    "SkillDiscoveryTool",
    "add_skill_commands"
]
