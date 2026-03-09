"""
HABOS 架构 - 决策层 (Decision Layer) 的一部分

此模块定义了主动行为库 (ActionLibrary) 和所有具体的主动行为 (Actions)。
它定义了 Agent "能做什么"。
"""
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, List

from crabclaw.bus.queue import MessageBus, OutboundMessage
from crabclaw.providers.base import LLMProvider
from crabclaw.proactive.state import InternalState
from crabclaw.proactive.triggers import TriggerEvent

if TYPE_CHECKING:
    from crabclaw.agent.tools.registry import ToolRegistry


class BaseAction(ABC):
    """
    所有主动行为的抽象基类 (策略模式)。
    """
    name: str = "base_action"
    description: str = "一个基础的主动行为描述。"
    cost: int = 10  # 执行此行为消耗的“打扰预算”

    @abstractmethod
    def matches(self, event: TriggerEvent) -> bool:
        """
        判断此行为是否是针对给定触发事件的合适响应。
        """
        pass

    @abstractmethod
    async def execute(
        self, state: InternalState, bus: MessageBus, provider: LLMProvider, tool_registry: "ToolRegistry"
    ) -> None:
        """
        执行具体的主动行为。
        """
        pass


# --- 具体行为实现示例 ---

class RemindUserUnresponsiveAction(BaseAction):
    """
    提醒型行为：当用户长时间未回复时，主动进行友好询问。
    """
    name: str = "remind_user_unresponsive"
    description: str = "当用户在进行中的任务上长时间未响应时，主动跟进询问。"
    cost: int = 5  # 这是一个低成本的提醒

    def matches(self, event: TriggerEvent) -> bool:
        # 此行为只响应“用户未响应”的风险触发事件
        return event.trigger_type == "risk_detected.user_unresponsive"

    async def execute(
        self, state: InternalState, bus: MessageBus, provider: LLMProvider
    ) -> None:
        risk_data = state.risks.get("user_unresponsive", {})
        days = risk_data.get("days", "几")
        topic = risk_data.get("topic", "我们之前的讨论")

        prompt = f"""
        你是一名专业的、有帮助的 AI 助手。你的用户已经 {days} 天没有就我们正在讨论的话题‘{topic}’作出回应。
        你的目标是发送一条温和、不催促的提醒，与他们确认一下情况，并表达你随时可以提供帮助。
        请保持专业、友好和简洁的语气，不要给用户带来压力。请直接生成这条消息的内容。
        """

        response = await provider.chat(messages=[{"role": "user", "content": prompt}])
        content = response.content

        session_key = risk_data.get("session_key")
        if not session_key or ":" not in session_key:
            # logger.error("Cannot execute reminder: session_key is missing or invalid in risk_data.")
            return

        target_channel, target_chat_id = session_key.split(":", 1)

        await bus.publish_outbound(
            OutboundMessage(channel=target_channel, chat_id=target_chat_id, content=content)
        )
        # 清除风险，避免重复触发
        if "user_unresponsive" in state.risks:
            del state.risks["user_unresponsive"]
            state.update_timestamp()


class AcquireSkillAction(BaseAction):
    """
    学习型行为：当发现能力短板时，主动从互联网上搜索并获取新技能。
    """
    name: str = "acquire_skill"
    description: str = "根据需求，从指定的技能库中搜索、下载并安装一个新的技能插件。"
    cost: int = 20 # 这是一个高成本的行为，因为它涉及网络和文件操作

    def matches(self, event: TriggerEvent) -> bool:
        # 此行为响应“需要新技能”的触发事件
        return event.trigger_type == "need_new_skill"

    async def execute(
        self, state: InternalState, bus: MessageBus, provider: LLMProvider, tool_registry: "ToolRegistry"
    ) -> None:
        skill_need = state.get_last_skill_need()
        if not skill_need:
            return

        spawn_tool = tool_registry.get("spawn")
        if not spawn_tool:
            return

        # 定义研究员子智能体的任务
        research_task = f"""
        你的任务是为我开发一个新的 crabclaw 技能，名为 '{skill_need['name']}'。
        这个技能需要实现以下功能: {skill_need['description']}。
        请遵循以下步骤:
        1. 使用 web_search 搜索相关的 Python 代码示例和实现方法。
        2. 使用 web_fetch 阅读和分析搜索到的内容。
        3. 根据 crabclaw 的技能和工具基类 (BaseSkill, BaseTool)，编写完整的技能代码。
        4. 使用 write_file 将最终的技能代码保存到 'skills/{skill_need['name']}.py' 文件中。
        5. 完成后，回复 '任务完成'。
        """

        # 启动子智能体并等待其完成
        subagent_id = await spawn_tool.execute(
            task=research_task,
            system_prompt_name="subagent_researcher"
        )
        # 在一个更完整的实现中，主 Agent 会在这里等待并监督子智能体的进度

        # 假设子智能体已成功完成任务，调用内部工具来重载技能
        reload_tool = tool_registry.get("reload_skills")
        if reload_tool:
            await reload_tool.execute()

        state.clear_last_skill_need()



# --- 行为库管理器 ---

class ActionLibrary:
    """
    管理和提供所有可用主动行为的库。
    """

    def __init__(self):
        self._actions: List[BaseAction] = []
        self._register_default_actions()

    def _register_default_actions(self):
        """注册所有默认的主动行为。"""
        self.add_action(RemindUserUnresponsiveAction())
        self.add_action(AcquireSkillAction())

    def add_action(self, action: BaseAction):
        self._actions.append(action)

    def get_available_actions(self) -> List[BaseAction]:
        return self._actions
