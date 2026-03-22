"""
The Psychology/Cognition Layer of the HAOS.

This module contains the core components of the agent's mind,
including the Global Workspace Theory implementation for consciousness
and the Emotion Engine.
"""
import asyncio
from typing import Dict, List

from .datatypes import Signal, Stimulus


class GlobalWorkspace:
    """
    Simulates the "consciousness bus" of the agent.

    It receives signals from all other cognitive modules and uses an
    attention mechanism to select the most salient ones to become the
    "focus of attention" for a given tick.
    """
    def __init__(self, capacity: int = 3):
        self.capacity = capacity
        self.stimulus_queue = asyncio.Queue()

    def add_stimulus(self, stimulus: Stimulus):
        """Allows external systems (like the IOProcessor) to add stimuli to the workspace."""
        self.stimulus_queue.put_nowait(stimulus)

    async def gather_stimuli(self) -> List[Stimulus]:
        """Gathers all pending stimuli from the queue for a given tick."""
        stimuli = []
        while not self.stimulus_queue.empty():
            stimuli.append(self.stimulus_queue.get_nowait())
        return stimuli

    def drain_stimuli(self) -> List[Stimulus]:
        stimuli = []
        while not self.stimulus_queue.empty():
            stimuli.append(self.stimulus_queue.get_nowait())
        return stimuli

    def select_focus(self, signals: List[Signal | Stimulus]) -> List[Signal | Stimulus]:
        """
        门控机制 (Gating Mechanism): 从所有信号中选择强度最高的进入意识。
        """
        if not signals:
            return []

        # Ensure all items have intensity (for Stimulus which might not have it defined as property)
        # In datatypes.py, Signal has intensity, Stimulus has content.
        # We assume all signals/stimuli passed here are valid.

        sorted_signals = sorted(signals, key=lambda s: getattr(s, 'intensity', 0.8), reverse=True)
        return sorted_signals[:self.capacity]

class EmotionEngine:
    def __init__(self):
        self.state = {
            "curiosity": 0.6,
            "confidence": 0.7,
            "risk_aversion": 0.4,
            "social_trust": 0.5,
        }

    def update_from_event(self, event: Dict):
        event_type = event.get("type")
        if event_type == "unexpected_positive_outcome":
            self.state["curiosity"] = min(1.0, self.state["curiosity"] + 0.2)
            self.state["confidence"] = min(1.0, self.state["confidence"] + 0.1)
        elif event_type == "action_success":
            self.state["confidence"] = min(1.0, self.state["confidence"] + 0.05)
            self.state["risk_aversion"] = max(0.0, self.state["risk_aversion"] - 0.05)
        elif event_type in {"action_failed_with_risk", "action_failure", "low_energy_warning"}:
            self.state["risk_aversion"] = min(1.0, self.state["risk_aversion"] + 0.3)
            self.state["confidence"] = max(0.0, self.state["confidence"] - 0.1)
        self.tick()

    def update(self, event: Dict):
        self.update_from_event(event)

    def tick(self):
        self.state["curiosity"] = min(1.0, max(0.0, self.state["curiosity"] * 0.995))
        self.state["confidence"] = min(1.0, max(0.0, self.state["confidence"] * 0.997))
        self.state["risk_aversion"] = min(1.0, max(0.0, self.state["risk_aversion"] * 0.995))
        self.state["social_trust"] = min(1.0, max(0.0, self.state["social_trust"] * 0.998))

    def get_decision_modulators(self) -> Dict:
        return {
            "exploration_bonus": self.state["curiosity"] * 0.5,
            "safety_bonus": self.state["risk_aversion"] * 0.8,
            "collaboration_bonus": self.state["social_trust"] * 0.6,
        }

    def get_emotional_modulation(self) -> Dict:
        return self.get_decision_modulators()

class PsychologySystem:
    """
    A container for all psychological components.
    """
    def __init__(self):
        self.workspace = GlobalWorkspace()
        self.emotion = EmotionEngine()

    def tick(self):
        """A single tick of the psychological clock."""
        # For now, most psychological logic is in the PersistentAgentLoop
        pass
