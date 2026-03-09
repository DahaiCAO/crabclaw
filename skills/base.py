"""
技能系统的基础定义。

定义了所有技能 (Skill) 和工具 (Tool) 必须遵守的接口。
"""
from abc import ABC, abstractmethod
from typing import List, Type


class BaseTool(ABC):
    """
    所有工具的抽象基类。
    一个工具是 Agent 可以执行的单个、具体的能力。
    """
    name: str = "base_tool"
    description: str = "这是一个基础工具。"
    
    @abstractmethod
    async def execute(self, **kwargs) -> str:
        """执行工具的具体逻辑。"""
        pass


class BaseSkill(ABC):
    """
    所有技能的抽象基类。
    一个技能是一个能力的集合，它向 Agent 提供一个或多个工具。
    """
    name: str = "base_skill"
    description: str = "这是一个基础技能包。"

    @abstractmethod
    def get_tools(self) -> List[Type[BaseTool]]:
        """返回此技能提供的所有工具的类。"""
        pass
