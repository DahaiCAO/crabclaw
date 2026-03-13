"""
HABOS Architecture - Core Engine for the Meta-Cognition Layer

This module defines the ReflectionEngine, which is an independent service running in the background.
It is responsible for reading audit logs, performing self-evaluation and optimization,
and enabling the autonomous evolution of the Agent.
"""
import asyncio
import json
import logging
import time
from typing import Any, Callable, Dict, List, Optional

from crabclaw.proactive.state import InternalState
from crabclaw.prompts.manager import PromptManager
from crabclaw.providers.base import LLMProvider

logger = logging.getLogger(__name__)


class ReflectionEngine:
    """
    Reflection Engine.
    """

    def __init__(
        self,
        state: InternalState,
        provider: LLMProvider,
        audit_log_path: str,
        prompt_manager: PromptManager,
        on_event: Callable[[dict], None] | None = None,
    ):
        self.state = state
        self.provider = provider
        self.audit_log_path = audit_log_path
        self.prompt_manager = prompt_manager
        self._on_event = on_event
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._last_log_timestamp_processed: float = state.last_reflection_ts

    def _emit(self, event: dict) -> None:
        if not self._on_event:
            return
        try:
            self._on_event(event)
        except Exception:
            return

    def _read_new_logs(self) -> List[Dict[str, Any]]:
        """Read all new audit logs since the last processing."""
        new_logs = []
        try:
            with open(self.audit_log_path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        log_entry = json.loads(line)
                        if log_entry["timestamp"] > self._last_log_timestamp_processed:
                            new_logs.append(log_entry)
                    except (json.JSONDecodeError, KeyError):
                        continue # Skip lines with incorrect format
        except FileNotFoundError:
            logger.warning(f"Audit log file not found at: {self.audit_log_path}")
            return []

        if new_logs:
            # Update processing timestamp to the latest log entry's timestamp
            self._last_log_timestamp_processed = new_logs[-1]["timestamp"]

        return new_logs

    async def run_goal_oracle(self, user_request: str, agent_response: str) -> Optional[dict]:
        """
        Run the "Goal Oracle" to determine if an interaction aligns with long-term goals.
        """
        prompt = self.prompt_manager.format(
            "reflection_goal_oracle",
            long_term_goal=self.state.long_term_goal,
            user_request=user_request,
            agent_response=agent_response
        )
        response = await self.provider.chat(messages=[{"role": "user", "content": prompt}])
        try:
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            return json.loads(content)
        except (json.JSONDecodeError, IndexError) as e:
            logger.error(f"Failed to parse Goal Oracle response: {e}")
            return None

    async def run_cycle(self):
        """
        Execute a complete reflection "perception-analysis-optimization" cycle.
        """
        logger.debug("Running reflection engine cycle...")

        log_entries = self._read_new_logs()
        if not log_entries:
            logger.debug("No new audit logs to reflect on.")
            return

        self._emit({"timestamp": time.time(), "stage": "logs_loaded", "count": len(log_entries)})

        logger.info(f"Reflecting on {len(log_entries)} new audit log entries.")

        # Update reflection timestamp in state
        self.state.last_reflection_ts = self._last_log_timestamp_processed
        self.state.update_timestamp()

        # 2. Extract complete interactions (request/response pairs) from logs
        #    This is a simplified implementation that assumes a request is immediately followed by a final response.
        #    A more complex implementation would need to handle multi-turn conversations and concurrency.
        interactions = self._extract_interactions(log_entries)

        for interaction in interactions:
            # 3. Run "Goal Oracle" for each interaction
            logger.debug("Running Goal Oracle for interaction...")
            oracle_result = await self.run_goal_oracle(
                interaction["request"], interaction["response"]
            )
            if oracle_result is not None:
                self._emit({
                    "timestamp": time.time(),
                    "stage": "goal_oracle",
                    "session_hint": interaction.get("session_key"),
                    "result": oracle_result,
                })
            if oracle_result and oracle_result.get("goal_alignment_score", 1.0) < 0.5:
                logger.warning(
                    f"Significant deviation detected! "
                    f"Score: {oracle_result['goal_alignment_score']}, "
                    f"Reason: {oracle_result['justification']}"
                )
                # 4. Trigger "Root Cause Analysis"
                optimization_hypothesis = await self.run_root_cause_analysis(
                    interaction["full_log_chain"],
                    oracle_result
                )
                if optimization_hypothesis:
                    logger.info(f"Generated optimization hypothesis: {optimization_hypothesis}")
                    self._emit({
                        "timestamp": time.time(),
                        "stage": "hypothesis",
                        "hypothesis": optimization_hypothesis,
                    })
                    # 5. Trigger "Internal Simulation Verification" and "Self-Optimization"
                    await self.verify_and_apply_hypothesis(
                        interaction, optimization_hypothesis
                    )

    async def verify_and_apply_hypothesis(
        self, interaction: Dict[str, Any], hypothesis: Dict[str, Any]
    ):
        """Internally simulate, verify, and finally apply an optimization hypothesis."""
        logger.info(f"Verifying hypothesis: {hypothesis}")

        # 1. Run internal simulation to get a "virtual" new response
        new_response_content = await self._run_internal_simulation(
            interaction, hypothesis
        )
        if new_response_content is None:
            logger.error("Internal simulation failed. Aborting hypothesis verification.")
            return

        # 2. Submit the new response to the "Goal Oracle" for scoring
        verification_result = await self.run_goal_oracle(
            interaction["request"], new_response_content
        )
        if not verification_result:
            logger.error("Goal Oracle failed during verification. Aborting.")
            return

        original_score = interaction.get("score", 0.3) # Assume original score is stored
        new_score = verification_result.get("goal_alignment_score", 0.0)
        logger.info(f"Verification result: New score {new_score:.2f} vs. Original score {original_score:.2f}")

        # 3. Compare verification results and decide whether to apply
        if new_score > original_score + 0.2: # Threshold to avoid minor fluctuations
            logger.info("Hypothesis verified successfully. Applying permanent optimization.")
            self._apply_permanent_optimization(hypothesis)
        else:
            logger.warning("Hypothesis verification failed. New score did not meet improvement threshold. Discarding change.")

    async def _run_internal_simulation(
        self, interaction: Dict[str, Any], hypothesis: Dict[str, Any]
    ) -> Optional[str]:
        """Create a temporary 'virtual Agent' to run simulation and return its response."""
        try:
            hypo_details = hypothesis.get("optimization_hypothesis", {})
            hypo_type = hypo_details.get("type")

            logger.info(f"Running internal simulation for hypothesis type: {hypo_type}")

            # 1. Create an isolated simulation environment
            # Deep copy state to ensure simulation doesn't affect real state
            virtual_state = self.state.model_copy(deep=True)

            # Create a temporary, modified PromptManager for this simulation
            virtual_prompt_manager = self._create_virtual_prompt_manager(hypothesis)
            if not virtual_prompt_manager:
                return None

            # Create a "virtual" reactive engine using virtual components
            # Note: This is a simplified factory method, a complete production implementation would need more robust dependency injection
            virtual_reactive_engine = self._create_virtual_reactive_engine(
                virtual_state, virtual_prompt_manager
            )

            # 2. Re-run the original request on the virtual engine
            logger.info("Executing request on virtual engine...")
            response = await virtual_reactive_engine.process_direct(
                interaction["request"], session_key="simulation"
            )
            return response.content if response else None

        except Exception as e:
            logger.error(f"Error during internal simulation: {e}", exc_info=True)
            return None

    def _create_virtual_prompt_manager(
        self, hypothesis: Dict[str, Any]
    ) -> Optional[PromptManager]:
        """Create a temporary, modified PromptManager for simulation."""
        from crabclaw.prompts.manager import PromptManager
        hypo_details = hypothesis.get("optimization_hypothesis", {})
        hypo_type = hypo_details.get("type")
        hypo_target = hypo_details.get("target")
        hypo_change = hypo_details.get("proposed_change")

        if hypo_type != "prompt_template_modification":
            # For non-prompt modifications, we can use the original prompt_manager
            return self.prompt_manager

        # Create a new PromptManager instance that inherits all existing templates
        virtual_manager = PromptManager(self.prompt_manager.templates_dir)
        # Directly override the template to be modified in memory
        if hypo_target in virtual_manager.templates:
            virtual_manager.templates[hypo_target]["template"] = hypo_change
            logger.debug(f"Virtual prompt manager created with modified template: {hypo_target}")
            return virtual_manager
        else:
            logger.error(f"Cannot create virtual prompt manager: target '{hypo_target}' not found.")
            return None

    def _create_virtual_reactive_engine(
        self, virtual_state: InternalState, virtual_prompt_manager: PromptManager
    ) -> "AgentLoop":
        """(Simplified factory) Create a reactive engine instance for simulation."""
        from crabclaw.agent.loop import AgentLoop

        # Note: Here we only replace the core provider and workspace,
        # a complete production implementation would need to handle all dependencies.
        return AgentLoop(
            bus=self.bus, # Share bus to receive responses
            provider=self.provider, # Share provider
            workspace=Path("~/.crabclaw/simulation_workspace"), # Use an isolated workspace
            internal_state=virtual_state,
            audit_logger=None, # Simulation process doesn't generate audit logs
            prompt_manager=virtual_prompt_manager
        )

    def _apply_permanent_optimization(self, hypothesis: Dict[str, Any]):
        """Permanently apply a verified optimization hypothesis to the Agent's configuration."""
        try:
            hypo_type = hypothesis.get("optimization_hypothesis", {}).get("type")
            hypo_target = hypothesis.get("optimization_hypothesis", {}).get("target")
            hypo_change = hypothesis.get("optimization_hypothesis", {}).get("proposed_change")

            if not all([hypo_type, hypo_target, hypo_change]):
                logger.error(f"Invalid hypothesis format: {hypothesis}")
                return

            if hypo_type == "state_parameter_adjustment":
                # Handle direct adjustment of InternalState parameters
                if hasattr(self.state, hypo_target):
                    current_value = getattr(self.state, hypo_target)
                    # Simple mathematical operation handling
                    if isinstance(current_value, (int, float)):
                        # Note: eval() has security risks, handled here in a very restricted manner
                        if hypo_change.startswith(("+", "-")):
                            new_value = current_value + float(hypo_change)
                        else:
                            new_value = float(hypo_change)
                        setattr(self.state, hypo_target, new_value)
                        logger.info(f"Adjusted state parameter '{hypo_target}' from {current_value} to {new_value}")
                        self.state.update_timestamp()
                    else:
                        logger.warning(f"Cannot apply arithmetic change to non-numeric state parameter '{hypo_target}'")
                else:
                    logger.error(f"Attempted to adjust non-existent state parameter: {hypo_target}")

            elif hypo_type == "prompt_template_modification":
                self.prompt_manager.save_template(hypo_target, hypo_change)
                logger.info(f"Applied prompt modification for '{hypo_target}'.")
                self._emit({
                    "timestamp": time.time(),
                    "stage": "applied",
                    "type": hypo_type,
                    "target": hypo_target,
                })

            else:
                logger.warning(f"Unknown hypothesis type: {hypo_type}")

        except Exception as e:
            logger.error(f"Failed to apply optimization hypothesis: {e}", exc_info=True)

    async def run_root_cause_analysis(
        self, log_chain: List[Dict[str, Any]], oracle_result: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Perform root cause analysis on low-scoring behavior and generate optimization hypotheses."""
        prompt = self.prompt_manager.format(
            "reflection_root_cause_analysis",
            long_term_goal=self.state.long_term_goal,
            goal_alignment_score=oracle_result.get('goal_alignment_score'),
            justification=oracle_result.get('justification'),
            log_chain_json=json.dumps(log_chain, indent=2, ensure_ascii=False)
        )
        response = await self.provider.chat(messages=[{"role": "user", "content": prompt}])
        try:
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            return json.loads(content)
        except (json.JSONDecodeError, IndexError) as e:
            logger.error(f"Failed to parse Root Cause Analysis response: {e}")
            return None

    def _extract_interactions(self, logs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract complete interaction chains by session_key from log entries."""
        sessions: Dict[str, List[Dict[str, Any]]] = {}
        for log in logs:
            session_key = log.get("details", {}).get("session_key")
            if session_key:
                if session_key not in sessions:
                    sessions[session_key] = []
                sessions[session_key].append(log)

        interactions = []
        for session_key, session_logs in sessions.items():
            # Simple assumption: The first InboundMessage in each session is the request, the last OutboundMessage is the response
            inbound_logs = [log for log in session_logs if log["event_type"] == "InboundMessage"]
            outbound_logs = [log for log in session_logs if log["event_type"] == "OutboundMessage"]

            if inbound_logs and outbound_logs:
                interactions.append({
                    "request": inbound_logs[0]["details"].get("content", ""),
                    "response": outbound_logs[-1]["details"].get("content", ""),
                    "full_log_chain": session_logs
                })
        return interactions

    async def _loop(self, interval_seconds: int):
        """
        Engine's main loop, regularly runs run_cycle.
        """
        self._running = True
        logger.info(f"Reflection Engine started with {interval_seconds}s interval.")
        while self._running:
            try:
                await self.run_cycle()
                await asyncio.sleep(interval_seconds)
            except asyncio.CancelledError:
                self._running = False
                break
            except Exception as e:
                logger.error(f"Error in reflection engine loop: {e}", exc_info=True)
                await asyncio.sleep(interval_seconds)
        logger.info("Reflection Engine stopped.")

    def start(self, interval_seconds: int = 3600):  # Default: reflect every hour
        """Start the reflection engine in the background."""
        if not self._running:
            self._task = asyncio.create_task(self._loop(interval_seconds))

    def stop(self):
        """Stop the reflection engine."""
        if self._task and not self._task.done():
            self._task.cancel()
