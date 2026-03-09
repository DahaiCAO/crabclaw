"""
HABOS 架构 - 决策层 (Decision Layer) 的核心

此模块定义了行为决策器 (ActionSelector)，它负责在所有可行的主动行为中，
根据价值评估模型，选择出最优的一个来执行。
它回答了"我该做什么？"这个问题。
"""
import json
from typing import Dict, List, Optional

from crabclaw.providers.base import LLMProvider
from crabclaw.prompts.manager import PromptManager
from crabclaw.proactive.library import ActionLibrary, BaseAction
from crabclaw.proactive.state import InternalState
from crabclaw.proactive.triggers import TriggerEvent


class ActionSelector:
    """
    行为决策器。
    根据触发事件和内部状态，利用 LLM 进行风险收益分析，决定采取哪个主动行为。
    """

    def __init__(
        self,
        provider: LLMProvider,
        prompt_manager: PromptManager, decision_threshold: float = 0.6
    ):
        self.provider = provider
        self.prompt_manager = prompt_manager
        self.decision_threshold = decision_threshold
        # 这是您设计的行为价值评估模型
        self.weights = {
            "goal_gain": 0.3,
            "risk_reduction": 0.3,
            "relationship_maintenance": 0.1,
            "long_term_benefit": 0.1,
            "interruption_cost": -0.2, # 负权重
        }

    async def _score_action_with_llm(
        self, state: InternalState, event: TriggerEvent, action: BaseAction
    ) -> Dict[str, float]:
        """
        使用 LLM 对一个候选行为的各个维度进行评分 (0.0 - 1.0)。
        """
        prompt = self.prompt_manager.format(
            "proactive_selector_scorer",
            long_term_goal=state.long_term_goal,
            user_profile_json=state.user_profile.model_dump_json(indent=2),
            event_description=event.description,
            interruption_budget=state.interruption_budget,
            action_name=action.name,
            action_description=action.description
        )

        # 在真实的实现中，需要使用能强制输出 JSON 的方法来增强稳定性
        response = await self.provider.chat(
            messages=[{"role": "user", "content": prompt}],
            # response_format={"type": "json_object"} # 理想情况
        )

        try:
            # 尝试解析 LLM 返回的可能包含在代码块中的 JSON
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            scores = json.loads(content)
        except (json.JSONDecodeError, IndexError) as e:
            # logger.error(f"Failed to parse LLM scoring response: {e}")
            scores = {} # 出错时返回空字典，避免崩溃

        return scores

    async def select_action(
        self, state: InternalState, events: List[TriggerEvent], action_library: ActionLibrary
    ) -> Optional[BaseAction]:
        """
        从所有可能的行为中选择最佳的一个。
        """
        best_action: Optional[BaseAction] = None
        highest_score: float = -1.0

        candidate_actions = [
            (event, action)
            for event in events
            for action in action_library.get_available_actions()
            if action.matches(event)
        ]

        if not candidate_actions:
            return None

        for event, action in candidate_actions:
            # 检查打扰预算
            if state.interruption_budget < action.cost:
                # logger.warning(f"Skipping action '{action.name}' due to insufficient interruption budget.")
                continue

            scores = await self._score_action_with_llm(state, event, action)

            final_score = sum(
                scores.get(dim, 0.0) * weight for dim, weight in self.weights.items()
            )

            if final_score > highest_score:
                highest_score = final_score
                best_action = action

        if highest_score > self.decision_threshold:
            # logger.info(f"Selected action '{best_action.name}' with score {highest_score:.2f}")
            return best_action
        else:
            # logger.info(f"No action selected. Highest score {highest_score:.2f} was below threshold {self.decision_threshold}.")
            return None
