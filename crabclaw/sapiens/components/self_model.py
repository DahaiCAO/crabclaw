"""
Component: SelfModel (Modeling System)

The agent's self-awareness module. It maintains the agent's understanding
of its own identity, state, skills, and personality. This is the core
of the "Identity Loop".
"""
from loguru import logger
from typing import Dict

from ..datatypes import Signal


class SelfModel:
    """Manages the agent's identity and current state (confidence, etc.)."""
    def __init__(self, personality: Dict, name: str = "ClawSapiens-001", nickname: str = ""):
        self.identity = {
            "name": name,
            "nickname": nickname,
            "personality": personality,
            "values": ["curiosity", "collaboration"],
            "skills": {"python_coding": 0.8, "data_analysis": 0.6},
        }
        self.state = {
            "confidence": 0.7,
            "energy": 0.9,
            "focus": 1.0,
            "current_goal": None,
        }

    def update_from_experience(self, outcome: dict):
        status = outcome.get("status")
        if status == "success":
            self.state["confidence"] = min(1.0, self.state["confidence"] + 0.05)
            skill = outcome.get("skill_used")
            if skill:
                self.identity["skills"][skill] = min(
                    1.0,
                    self.identity["skills"].get(skill, 0.0) + 0.01,
                )
            logger.debug(f"[SelfModel] Confidence increased. Current confidence: {self.state['confidence']:.2f}")
        elif status == "failure":
            self.state["confidence"] = max(0.0, self.state["confidence"] - 0.1)
            logger.debug(f"[SelfModel] Confidence decreased. Current confidence: {self.state['confidence']:.2f}")

    def get_self_awareness_signal(self) -> Signal | None:
        if self.state["confidence"] < 0.3:
            return Signal(
                source="SelfModel",
                content="Low Confidence Warning",
                intensity=0.8,
                metadata={"suggestion": "Seek simpler tasks or ask for help"},
            )
        return None
