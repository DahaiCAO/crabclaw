"""
HABOS Architecture - Active Channel Engine for the Decision Layer

This module defines the ProactiveEngine, which is an independent service running in the background.
It is responsible for driving the Agent to think autonomously and take proactive actions when there is no external input.
"""
import asyncio
import logging
import time
from typing import Optional

from crabclaw.agent.tools.registry import ToolRegistry
from crabclaw.bus.queue import MessageBus
from crabclaw.proactive.library import ActionLibrary
from crabclaw.proactive.selector import ActionSelector
from crabclaw.proactive.state import InternalState
from crabclaw.proactive.triggers import TriggerSystem
from crabclaw.prompts.manager import PromptManager
from crabclaw.providers.base import LLMProvider

# Configure logger
logger = logging.getLogger(__name__)


class ProactiveEngine:
    """
    Proactive Engine.
    """

    def __init__(
        self,
        state: InternalState,
        bus: MessageBus,
        provider: LLMProvider,
        prompt_manager: PromptManager,
        tool_registry: "ToolRegistry",
        # Can be injected externally in the future for better dependency management
        trigger_system: Optional[TriggerSystem] = None,
        action_library: Optional[ActionLibrary] = None,
        action_selector: Optional[ActionSelector] = None,
    ):
        self.state = state
        self.bus = bus
        self.provider = provider
        self.prompt_manager = prompt_manager
        self.tool_registry = tool_registry

        # Assemble the three core components
        self.triggers = trigger_system or TriggerSystem()
        self.library = action_library or ActionLibrary()
        self.selector = action_selector or ActionSelector(provider=self.provider, prompt_manager=self.prompt_manager)

        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def run_cycle(self):
        """
        Execute a complete proactive "perception-thinking-decision-action" cycle.
        """
        logger.debug("Running proactive engine cycle...")

        # 1. Perception layer: Check trigger conditions
        triggered_events = self.triggers.check(self.state)
        if not triggered_events:
            logger.debug("No proactive triggers met.")
            return

        logger.info(f"Proactive triggers met: {triggered_events}")

        # 2. Decision layer: Select the best action
        best_action = await self.selector.select_action(
            self.state, triggered_events, self.library
        )
        if not best_action:
            logger.info("Action selector decided not to act.")
            return

        logger.info(f"Executing proactive action: {best_action.name}")
        try:
            # 3. Execution layer: Execute the action
            await best_action.execute(self.state, self.bus, self.provider, self.tool_registry)

            # 4. Motivation layer update: Update state and budget
            self.state.last_proactive_ts = time.time()
            self.state.interruption_budget -= best_action.cost
            self.state.update_timestamp()
            # self.save_state() # Persistence should be handled by the main scheduler
            logger.info(
                f"Proactive action '{best_action.name}' executed. "
                f"Interruption budget remaining: {self.state.interruption_budget}"
            )
        except Exception as e:
            logger.error(f"Error executing proactive action '{best_action.name}': {e}", exc_info=True)

    async def _loop(self, interval_seconds: int):
        """
        Engine's main loop, regularly runs run_cycle.
        """
        self._running = True
        logger.info(f"Proactive Engine started with {interval_seconds}s interval.")
        while self._running:
            try:
                await self.run_cycle()
                await asyncio.sleep(interval_seconds)
            except asyncio.CancelledError:
                self._running = False
                break
            except Exception as e:
                logger.error(f"Error in proactive engine loop: {e}", exc_info=True)
                # Avoid the entire loop crashing due to a single error, wait for the next cycle
                await asyncio.sleep(interval_seconds)
        logger.info("Proactive Engine stopped.")

    def start(self, interval_seconds: int = 60):
        """Start the proactive engine in the background."""
        if not self._running:
            self._task = asyncio.create_task(self._loop(interval_seconds))

    def stop(self):
        """Stop the proactive engine."""
        if self._task and not self._task.done():
            self._task.cancel()
