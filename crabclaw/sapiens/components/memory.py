"""
Component: MemorySystem

Implements the three-tiered memory architecture:
1. Episodic (Experiences)
2. Semantic (Knowledge)
3. Procedural (Skills)
"""

import collections
import time
from typing import List

from ..datatypes import Signal, Stimulus


class WorkingMemory:
    """A short-term buffer for the current focus of attention."""
    def __init__(self, capacity: int = 10):
        self.capacity = capacity
        self.buffer = collections.deque(maxlen=capacity)

    def add_focus(self, focus: List[Signal | Stimulus]):
        """Adds the current conscious focus to working memory."""
        for item in focus:
            self.buffer.append(item)

    def get_context(self) -> List[Signal | Stimulus]:
        """Returns the current contents of working memory as context."""
        return list(self.buffer)

class EpisodicMemory:
    """Long-term storage for personal experiences ("I remember when...")."""
    def __init__(self):
        self.storage = []

    def store_experience(self, event: str, emotions: dict, outcome: dict):
        self.storage.append({
            "event": event,
            "emotions": emotions.copy(),
            "outcome": outcome,
            "timestamp": time.time(),
        })

    def get_recent(self, limit: int = 20) -> list[dict]:
        return self.storage[-limit:]

class SemanticMemory:
    """Long-term storage for objective facts ("I know that...")."""
    def __init__(self):
        self.facts = {}

    def add_fact(self, key: str, value: str):
        self.facts[key] = value

class ProceduralMemory:
    """Long-term storage for skills and abilities ("I know how to...")."""
    def __init__(self, tool_registry):
        self.skills = tool_registry or {}

class MemorySystem:
    """A container for all memory components."""
    def __init__(self, tool_registry):
        self.working = WorkingMemory()
        self.episodic = EpisodicMemory()
        self.semantic = SemanticMemory()
        self.procedural = ProceduralMemory(tool_registry)

    def reflect_and_abstract(self):
        recent = self.episodic.get_recent(limit=10)
        if not recent:
            return None
        failures = [x for x in recent if x["outcome"].get("status") == "failure"]
        successes = [x for x in recent if x["outcome"].get("status") == "success"]
        self.semantic.add_fact("recent_success_count", str(len(successes)))
        self.semantic.add_fact("recent_failure_count", str(len(failures)))
        return {
            "successes": len(successes),
            "failures": len(failures),
        }
