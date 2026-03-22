"""Agent core module."""

from crabclaw.agent.context import ContextBuilder
from crabclaw.agent.memory import MemoryStore
from crabclaw.agent.skills import SkillsLoader

try:
    from crabclaw.agent.loop import AgentLoop
except ImportError:
    AgentLoop = None

__all__ = ["AgentLoop", "ContextBuilder", "MemoryStore", "SkillsLoader"]
