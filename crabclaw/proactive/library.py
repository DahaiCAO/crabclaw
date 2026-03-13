"""
HABOS Architecture - Part of the Decision Layer

This module defines the ActionLibrary and all concrete proactive actions.
It defines what the Agent "can do".
"""
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, List

from crabclaw.bus.queue import MessageBus, OutboundMessage
from crabclaw.proactive.state import InternalState
from crabclaw.proactive.triggers import TriggerEvent
from crabclaw.providers.base import LLMProvider

if TYPE_CHECKING:
    from crabclaw.agent.tools.registry import ToolRegistry


class BaseAction(ABC):
    """
    Abstract base class for all proactive actions (strategy pattern).
    """
    name: str = "base_action"
    description: str = "A basic proactive action description."
    cost: int = 10  # "Disturbance budget" consumed by executing this behavior

    @abstractmethod
    def matches(self, event: TriggerEvent) -> bool:
        """
        Determine if this action is an appropriate response to the given trigger event.
        """
        pass

    @abstractmethod
    async def execute(
        self, state: InternalState, bus: MessageBus, provider: LLMProvider, tool_registry: "ToolRegistry"
    ) -> None:
        """
        Execute the specific proactive action.
        """
        pass


# --- Concrete Action Implementations ---

class RemindUserUnresponsiveAction(BaseAction):
    """
    Reminder action: Proactively ask friendly questions when the user hasn't responded for a long time.
    """
    name: str = "remind_user_unresponsive"
    description: str = "Proactively follow up when the user has been unresponsive on an ongoing task for a long time."
    cost: int = 5  # This is a low-cost reminder

    def matches(self, event: TriggerEvent) -> bool:
        # This action only responds to "user unresponsive" risk trigger events
        return event.trigger_type == "risk_detected.user_unresponsive"

    async def execute(
        self, state: InternalState, bus: MessageBus, provider: LLMProvider
    ) -> None:
        risk_data = state.risks.get("user_unresponsive", {})
        days = risk_data.get("days", "several")
        topic = risk_data.get("topic", "our previous discussion")

        prompt = f"""
        You are a professional, helpful AI assistant. Your user has not responded to our discussion about '{topic}' for {days} days.
        Your goal is to send a gentle, non-pushy reminder to check in with them and express that you're available to help anytime.
        Please maintain a professional, friendly, and concise tone, and don't pressure the user. Please directly generate the content of this message.
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
        # Clear the risk to avoid repeated triggers
        if "user_unresponsive" in state.risks:
            del state.risks["user_unresponsive"]
            state.update_timestamp()


class AcquireSkillAction(BaseAction):
    """
    Learning action: Proactively search and acquire new skills from the internet when capability gaps are identified.
    """
    name: str = "acquire_skill"
    description: str = "Search, download, and install a new skill plugin from the specified skill library based on requirements."
    cost: int = 20 # This is a high-cost action because it involves network and file operations

    def matches(self, event: TriggerEvent) -> bool:
        # This action responds to "need new skill" trigger events
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

        # Define the researcher sub-agent's task
        research_task = f"""
        Your task is to develop a new crabclaw skill for me called '{skill_need['name']}'.
        This skill needs to implement the following functionality: {skill_need['description']}.
        Please follow these steps:
        1. Use web_search to search for relevant Python code examples and implementation methods.
        2. Use web_fetch to read and analyze the searched content.
        3. Based on crabclaw's skill and tool base classes (BaseSkill, BaseTool), write complete skill code.
        4. Use write_file to save the final skill code to 'skills/{skill_need['name']}.py' file.
        5. After completion, reply with 'Task completed'.
        """

        # Start the sub-agent and wait for it to complete
        subagent_id = await spawn_tool.execute(
            task=research_task,
            system_prompt_name="subagent_researcher"
        )
        # In a more complete implementation, the main Agent would wait here and monitor the sub-agent's progress

        # Assuming the sub-agent has successfully completed the task, call the internal tool to reload skills
        reload_tool = tool_registry.get("reload_skills")
        if reload_tool:
            await reload_tool.execute()

        state.clear_last_skill_need()



# --- Action Library Manager ---

class ActionLibrary:
    """
    Library that manages and provides all available proactive actions.
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
