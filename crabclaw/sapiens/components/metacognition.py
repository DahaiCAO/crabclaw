"""
Component: MetaCognition (Meta-Cognition System)

The "observer of the self". This module monitors the agent's own thought
processes, identifies cognitive biases or loops, and can trigger
strategy changes. This is the core of the "Meta Loop".
"""

from ..datatypes import Action, Signal, Thought
from .memory import MemorySystem


class ReflectionSystem:
    """Periodically reviews episodic memory and summarizes it into semantic knowledge."""
    def __init__(self, memory: MemorySystem):
        self.memory = memory

    def reflect(self):
        return self.memory.reflect_and_abstract()

class MetaCognition:
    """Monitors the agent's own reasoning and can trigger self-correction."""
    def __init__(self):
        self.decision_trace = []
        self._pending_strategy_signal: Signal | None = None

    def review_last_decision(self, thought: Thought, action: Action, outcome: dict):
        self.decision_trace.append({
            "thought": thought,
            "action": action,
            "outcome": outcome,
        })
        if outcome.get("status") == "failure":
            self._pending_strategy_signal = Signal(
                source="MetaCognition",
                content="Strategy Adjustment Needed",
                intensity=0.95,
                urgency=0.8,
                metadata={"last_action": action.name},
            )
            return self._pending_strategy_signal
        self._pending_strategy_signal = None
        return None

    def consume_strategy_signal(self) -> Signal | None:
        signal = self._pending_strategy_signal
        self._pending_strategy_signal = None
        return signal
