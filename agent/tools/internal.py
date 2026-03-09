"""
专供 Agent 自身使用的内部工具。
这些工具通常不应该暴露给最终用户。
"""
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from crabclaw.skills.manager import SkillManager


class ReloadSkillsTool:
    """
    一个内部工具，用于在运行时重新加载所有技能。
    """
    name: str = "reload_skills"
    description: str = "(内部工具) 重新扫描技能目录，并加载任何新发现的技能。"

    def __init__(self, skill_manager: "SkillManager"):
        self.skill_manager = skill_manager

    async def execute(self) -> str:
        """执行技能重载并返回结果。"""
        try:
            self.skill_manager.load_skills()
            return "技能库已成功刷新。"
        except Exception as e:
            # logger.error(f"Failed to reload skills: {e}", exc_info=True)
            return f"刷新技能库时发生错误: {e}"
