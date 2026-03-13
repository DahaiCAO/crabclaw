"""
技能管理器 (SkillManager)

负责在运行时动态地发现、加载和管理所有技能插件。
"""
import importlib.util
import inspect
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from crabclaw.skills.base import BaseSkill

if TYPE_CHECKING:
    from crabclaw.agent.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class SkillManager:
    """
    动态发现、加载和管理技能插件。
    """

    def __init__(self, skills_dir: Path, tool_registry: "ToolRegistry"):
        self.skills_dir = skills_dir
        self.tool_registry = tool_registry
        if not self.skills_dir.exists():
            logger.info(f"Skills directory not found, creating at: {self.skills_dir}")
            self.skills_dir.mkdir(parents=True, exist_ok=True)

    def load_skills(self):
        """扫描技能目录，加载所有技能，并将其工具注册到工具库中。"""
        logger.info(f"Loading skills from directory: {self.skills_dir}")
        for file_path in self.skills_dir.glob("**/*.py"):
            if file_path.name.startswith(("__", "base", "manager")):
                continue
            
            try:
                self._load_skill_from_file(file_path)
            except Exception as e:
                logger.error(f"Failed to load skill from {file_path}: {e}", exc_info=True)

    def _load_skill_from_file(self, file_path: Path):
        """从单个 Python 文件中加载技能。"""
        module_name = f"crabclaw.skills.{file_path.stem}"
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if not spec or not spec.loader:
            logger.warning(f"Could not create module spec for {file_path}")
            return

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, BaseSkill) and obj is not BaseSkill:
                skill_instance = obj()
                logger.info(f"Discovered skill: {skill_instance.name}")
                
                # Instantiate and register all tools provided by this skill
                for tool_class in skill_instance.get_tools():
                    tool_instance = tool_class()
                    self.tool_registry.register(tool_instance)
                    logger.info(f"  - Registered tool: {tool_instance.name}")
