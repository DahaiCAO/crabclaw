"""
The main entry point for the AgentSapiens instance.

This class initializes and holds references to all the cognitive systems
and layers that constitute the agent's mind.
"""
from loguru import logger
import asyncio
import queue
from pathlib import Path
from typing import Any

try:
    from clawlink.protocol.envelope import MessageEnvelope
except ImportError:
    MessageEnvelope = Any

from crabclaw.agent.prompt_evolution import PromptEvolutionPipeline

from .components.action import ActionSystem
from .components.axiology import AxiologySystem
from .components.memory import MemorySystem
from .components.metacognition import MetaCognition, ReflectionSystem
from .components.needs import NeedsEngine
from .components.reasoning import ThinkingSystem
from .components.self_model import SelfModel
from .components.world_model import WorldModel
from .datatypes import Stimulus
from .loop import PersistentAgentLoop
from .physiology import PhysiologySystem
from .psychology import PsychologySystem
from .sociology import SociologySystem


class AgentSapiens:
    """
    The AgentSapiens represents a complete, autonomous, human-like digital entity.
    It integrates all cognitive, physiological, and social systems into a cohesive whole,
    driven by a persistent life loop.
    """
    def __init__(
        self,
        agent_id: str,
        personality_drives: dict,
        name: str | None = None,
        nickname: str | None = None,
        age: float = 0.0,
        gender: str = "non-binary",
        height: float = 175.0,
        weight: float = 70.0,
        hobbies: list[str] | None = None,
        tool_registry=None,
        workspace_path: Path | str | None = None,
        llm_provider=None,
    ):
        """
        Initializes the AgentSapiens.

        Args:
            agent_id: A unique identifier for this agent instance.
            personality_drives: A dictionary defining the agent's innate "six desires",
                                which influences its long-term behavior.
            name: The display name of the agent.
            nickname: The nickname of the agent.
            age: Initial age of the agent.
            gender: Gender of the agent.
            height: Height in cm.
            weight: Weight in kg.
            hobbies: List of hobbies.
            tool_registry: The registry of available tools/skills.
        """
        self.id = agent_id
        self.name = name or agent_id
        self.nickname = nickname or ""
        self.is_alive = True
        # Thread-safe queues for cross-thread interaction with IOProcessor.
        self.outbound_action_queue = queue.Queue()
        self.collaboration_inbox = queue.Queue()
        self.dialogue_inbox = queue.Queue()
        self.event_inbox = queue.Queue()
        self.workspace_path = Path(workspace_path).expanduser().resolve() if workspace_path else None
        self.prompt_evolution = (
            PromptEvolutionPipeline(self.workspace_path) if self.workspace_path is not None else None
        )
        self.llm_provider = llm_provider

        # Initialize the 4 layers
        self.physiology = PhysiologySystem()
        # Initialize age_ticks based on age
        if hasattr(self.physiology, "lifecycle"):
            self.physiology.lifecycle.age_ticks = int(age * self.physiology.lifecycle.TICK_PER_YEAR)

        self.psychology = PsychologySystem()
        self.sociology = SociologySystem(agent_id)
        self.axiology = AxiologySystem(
            values=["truthfulness", "collaboration", "efficiency"],
            mission="To become the most reliable AI assistant for complex data analysis."
        )

        # Initialize core components
        self.needs_engine = NeedsEngine(personality_drives=personality_drives)
        self.memory_system = MemorySystem(tool_registry=tool_registry)
        self.thinking_system = ThinkingSystem()
        self.self_model = SelfModel(
            personality=personality_drives,
            name=self.name,
            nickname=self.nickname
        )
        # Set additional identity fields
        self.self_model.identity.update({
            "age": age,
            "gender": gender,
            "height": height,
            "weight": weight,
            "hobbies": hobbies or []
        })
        
        self.world_model = WorldModel()
        self.meta_cognition = MetaCognition()
        self.reflection_system = ReflectionSystem(memory=self.memory_system)

        # Initialize action system with axiology for arbitration
        self.action_system = ActionSystem(
            physiology=self.physiology,
            sociology=self.sociology,
            axiology=self.axiology,
            llm_provider=self.llm_provider
        )

        # The core heartbeat of the agent, passing a reference to self
        self.loop = PersistentAgentLoop(self)
        logger.info(f"AgentSapiens '{self.id}' has been born.")

    def enqueue_cognitive_stimulus(self, entrypoint: str, stimulus: Stimulus):
        if entrypoint == "collaboration":
            self.collaboration_inbox.put_nowait(stimulus)
            return
        if entrypoint == "event":
            self.event_inbox.put_nowait(stimulus)
            return
        self.dialogue_inbox.put_nowait(stimulus)

    def route_protocol_envelope(self, envelope: MessageEnvelope):
        intent = (envelope.intent or "").lower()
        if intent in {"task.propose", "task.request"}:
            entrypoint = "collaboration"
            stimulus_type = "collaboration_task"
        elif intent in {"event.notify"}:
            entrypoint = "event"
            stimulus_type = "agent_event"
        elif intent in {"task.response"}:
            entrypoint = "dialogue"
            stimulus_type = "agent_response"
        else:
            entrypoint = "dialogue"
            stimulus_type = "agent_message"
        payload = envelope.content or {}
        message = str(payload.get("message", payload))
        stimulus = Stimulus(
            source=f"agent:{envelope.from_agent}",
            type=stimulus_type,
            content={
                "text": message,
                "intent": envelope.intent,
                "trace_id": envelope.trace_id,
                "reply_to": envelope.reply_to,
                "metadata": payload.get("metadata", {}),
            },
            timestamp=envelope.created_at,
        )
        self.enqueue_cognitive_stimulus(entrypoint, stimulus)

    def drain_cognitive_ingress(self) -> list[Stimulus]:
        stimuli: list[Stimulus] = []
        for inbox in (self.collaboration_inbox, self.dialogue_inbox, self.event_inbox):
            while True:
                try:
                    stimuli.append(inbox.get_nowait())
                except queue.Empty:
                    break
        return stimuli

    def live(self):
        """
        Starts the agent's persistent life loop.
        This is the main blocking call that keeps the agent "alive".
        """
        self.loop.run()

    async def get_outbound_action(self):
        """Allows external systems (like the IOProcessor) to get the next action."""
        return await asyncio.to_thread(self.outbound_action_queue.get)

    def shutdown(self):
        """
        Gracefully shuts down the agent's life loop.
        """
        self.is_alive = False
        self.loop.stop()
        print(f"AgentSapiens '{self.id}' is shutting down.")
