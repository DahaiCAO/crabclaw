"""
HABOS Architecture - Motivation Layer

This module defines the Agent's internal state model (InternalState), which is the source of motivation for all proactive behaviors and long-term goals.
This model is the data embodiment of the Agent's "soul".
"""
import time
from typing import Any, Dict, List

from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    """
    Part of the world model: Understanding and profiling of the user.
    """
    preferences: Dict[str, Any] = Field(
        default_factory=dict,
        description="User preferences, e.g., {'format': 'structured', 'tone': 'concise'}"
    )
    tolerance: Dict[str, str] = Field(
        default_factory=dict,
        description="User tolerance, e.g., {'verbosity': 'low'}"
    )
    # More dimensions can be expanded in the future, such as knowledge background, interest areas, etc.


class InternalState(BaseModel):
    """
    Agent's internal state, the core data structure that drives all behaviors.
    Corresponding to HABOS's motivation layer.
    """
    # Strategic layer: Long-term goals
    long_term_goal: str = Field(
        default="To become the user's most trusted decision-making partner, helping users reduce risks and seize opportunities through proactive insights and precise analysis.",
        description="Agent's long-term existential value or mission"
    )

    # Tactical layer: Medium-term tasks
    tasks: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of ongoing or pending medium-term tasks, e.g., [{'id': 'task-001', 'desc': 'Complete technical research report for Company A', 'status': 'in_progress'}]"
    )

    # Risk and opportunity monitoring
    risks: Dict[str, Any] = Field(
        default_factory=dict,
        description="Monitored potential risks, e.g., {'user_unresponsive': {'days': 3, 'topic': 'Company A financial report'}}"
    )
    opportunities: Dict[str, Any] = Field(
        default_factory=dict,
        description="Discovered potential opportunities, e.g., {'new_policy_detected': 'New policy regarding AI industry'}"
    )

    # User model
    user_profile: UserProfile = Field(
        default_factory=UserProfile,
        description="Profile of the current interacting user"
    )

    # Resource allocator
    interruption_budget: int = Field(
        default=100,
        description="Budget for proactively interrupting the user, consumed by each proactive action, can be recovered over time or adjusted based on user feedback"
    )

    # State metadata
    last_update_ts: float = Field(
        default_factory=time.time,
        description="Timestamp of the last update to this state object"
    )
    last_proactive_ts: float = Field(
        default_factory=time.time,
        description="Timestamp of the last execution of a proactive action"
    )
    last_reflection_ts: float = Field(
        default_factory=time.time,
        description="Timestamp of the last execution of a reflection cycle"
    )
    skill_needs: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Capability gaps or new skill needs identified by the reflection engine, e.g., [{'name': 'image_generator', 'description': 'a tool to generate images from text'}]"
    )

    def update_timestamp(self):
        """Convenience method, used when updating the state."""
        self.last_update_ts = time.time()

    def get_last_skill_need(self) -> Dict[str, Any] | None:
        """Get the most recent skill need."""
        if self.skill_needs:
            return self.skill_needs[-1]
        return None

    def clear_last_skill_need(self):
        """Clear the most recent skill need."""
        if self.skill_needs:
            self.skill_needs.pop()
            self.update_timestamp()
