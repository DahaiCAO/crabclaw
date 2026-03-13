"""
HABOS Architecture - Part of the Perception Layer

This module defines the TriggerSystem, which is responsible for monitoring internal state,
identifying conditions that require initiating proactive behavior (such as risks, opportunities, idle time, etc.).
"""
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from crabclaw.proactive.state import InternalState


class TriggerEvent:
    """
    Structured event object generated when a trigger condition is met.
    This is the information passed from the "Perception Layer" to the "Decision Layer".
    """

    def __init__(
        self, trigger_type: str, description: str, metadata: Optional[Dict[str, Any]] = None
    ):
        self.trigger_type = trigger_type
        self.description = description
        self.metadata = metadata or {}

    def __repr__(self):
        return f"TriggerEvent(type='{self.trigger_type}', desc='{self.description}')"


class BaseTrigger(ABC):
    """Abstract base class for all concrete triggers (strategy pattern)."""

    @abstractmethod
    def check(self, state: InternalState) -> Optional[TriggerEvent]:
        """
        Check if the trigger condition is met.
        If met, return a TriggerEvent object; otherwise return None.
        """
        pass


# --- Concrete Trigger Implementations ---

class RiskTrigger(BaseTrigger):
    """Risk trigger: Check various risks recorded in the internal state."""

    def check(self, state: InternalState) -> Optional[TriggerEvent]:
        # Example: Check if user has been unresponsive for a long time
        if "user_unresponsive" in state.risks:
            risk_data = state.risks["user_unresponsive"]
            days = risk_data.get("days", 0)
            if days >= 3:  # Threshold can be configured
                return TriggerEvent(
                    trigger_type="risk_detected.user_unresponsive",
                    description=f"User has not responded on '{risk_data.get('topic', 'an important topic')}' for {days} days.",
                    metadata=risk_data,
                )
        # More risk types can be added here, such as "market data expired" etc.
        return None


class GoalUnfinishedTrigger(BaseTrigger):
    """Goal unfinished trigger: Check if there are ongoing tasks."""

    def check(self, state: InternalState) -> Optional[TriggerEvent]:
        in_progress_tasks = [t for t in state.tasks if t.get("status") == "in_progress"]
        if in_progress_tasks:
            return TriggerEvent(
                trigger_type="goal_unfinished",
                description=f"There are {len(in_progress_tasks)} ongoing tasks that need attention.",
                metadata={"tasks": in_progress_tasks},
            )
        return None


class IdleTimeTrigger(BaseTrigger):
    """Idle time trigger: Check if Agent has not been proactively interacting for a long time."""

    def __init__(self, idle_seconds: int = 3600 * 24):  # Default is 24 hours
        self.idle_seconds = idle_seconds

    def check(self, state: InternalState) -> Optional[TriggerEvent]:
        current_time = time.time()
        if (current_time - state.last_proactive_ts) > self.idle_seconds:
            return TriggerEvent(
                trigger_type="long_idle_time",
                description=f"Agent has not been proactively interacting for more than {self.idle_seconds / 3600:.1f} hours.",
                metadata={"idle_seconds": self.idle_seconds},
            )
        return None


# --- Trigger System Manager ---

class TriggerSystem:
    """
    System that manages and runs all triggers.
    """

    def __init__(self):
        self._triggers: List[BaseTrigger] = []
        self._register_default_triggers()

    def _register_default_triggers(self):
        """Register all default triggers. Can be dynamically loaded from configuration in the future."""
        self.add_trigger(RiskTrigger())
        self.add_trigger(GoalUnfinishedTrigger())
        self.add_trigger(IdleTimeTrigger(idle_seconds=3600 * 8)) # Shortened time for testing

    def add_trigger(self, trigger: BaseTrigger):
        self._triggers.append(trigger)

    def check(self, state: InternalState) -> List[TriggerEvent]:
        """
        Run all registered triggers and collect all triggered events.
        """
        triggered_events = []
        for trigger in self._triggers:
            event = trigger.check(state)
            if event:
                triggered_events.append(event)
        return triggered_events
