"""
HABOS Architecture - Core of the Decision Layer

This module defines the ActionSelector, which is responsible for selecting the optimal one to execute
from all feasible proactive actions based on a value evaluation model.
It answers the question "What should I do?".
"""
import json
from typing import Dict, List, Optional

from crabclaw.proactive.library import ActionLibrary, BaseAction
from crabclaw.proactive.state import InternalState
from crabclaw.proactive.triggers import TriggerEvent
from crabclaw.templates.manager import PromptManager
from crabclaw.providers.base import LLMProvider


class ActionSelector:
    """
    Action Selector.
    Based on trigger events and internal state, use LLM to perform risk-benefit analysis and decide which proactive action to take.
    """

    def __init__(
        self,
        provider: LLMProvider,
        prompt_manager: PromptManager, decision_threshold: float = 0.6
    ):
        self.provider = provider
        self.prompt_manager = prompt_manager
        self.decision_threshold = decision_threshold
        # This is your designed action value evaluation model
        self.weights = {
            "goal_gain": 0.3,
            "risk_reduction": 0.3,
            "relationship_maintenance": 0.1,
            "long_term_benefit": 0.1,
            "interruption_cost": -0.2, # Negative weight
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

        # In a real implementation, need to use methods that can force JSON output to enhance stability
        response = await self.provider.chat(
            messages=[{"role": "user", "content": prompt}],
            # response_format={"type": "json_object"} # Ideal case
        )

        try:
            # Try to parse JSON that LLM returns, which may be contained in code blocks
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            scores = json.loads(content)
        except (json.JSONDecodeError, IndexError):
            # logger.error(f"Failed to parse LLM scoring response: {e}")
            scores = {} # Return empty dictionary on error to avoid crash

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
            # Check interruption budget
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
