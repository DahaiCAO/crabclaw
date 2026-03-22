"""
The Persistent Agent Loop - The Heartbeat of the HAOS.

This module contains the core `while self.is_alive:` loop that drives the
agent's existence, ensuring continuous perception, thought, and action,
independent of external triggers.
"""
import threading
import time
import asyncio
from typing import TYPE_CHECKING
from loguru import logger

from .datatypes import Action

if TYPE_CHECKING:
    from .agent import AgentSapiens

TICK_INTERVAL = 1.0  # Seconds per tick

class PersistentAgentLoop:
    """
    Manages the continuous, rhythmic cycle of the agent's life.
    It orchestrates the interaction between all cognitive modules in each "moment".
    """
    def __init__(self, agent: "AgentSapiens"):
        """
        Initializes the loop.

        Args:
            agent: A reference to the main AgentSapiens instance.
        """
        self.agent = agent
        self._stop_event = threading.Event()

    def run(self):
        """
        The main `while` loop that constitutes the agent's life.
        """
        logger.info(f"[Loop] Agent '{self.agent.id}' life loop starting.")
        while not self._stop_event.is_set():
            self.agent.physiology.tick()
            self.agent.psychology.tick()
            self.agent.sociology.tick()
            self.agent.needs_engine.tick()
            self.agent.psychology.emotion.tick()
            self.agent.needs_engine.set_need(
                "energy",
                self.agent.physiology.metabolism.energy / max(1.0, self.agent.physiology.metabolism.energy_max),
            )
            self.agent.sociology.economy.refresh()
            logger.info(
                f"[Tick {self.agent.physiology.lifecycle.age_ticks}] "
                f"Energy: {self.agent.physiology.metabolism.energy:.2f}, "
                f"Satiety: {self.agent.physiology.metabolism.satiety:.2f}, "
                f"Credits: {self.agent.sociology.economy.credits:.2f}, "
                f"Emotion: {self.agent.psychology.emotion.state}"
            )

            if not self.agent.physiology.metabolism.is_alive():
                self.agent.is_alive = False
                logger.warning(f"[Loop] Agent '{self.agent.id}' has run out of energy.")
                break

            internal_signals = (
                self.agent.physiology.get_signals()
                + self.agent.sociology.get_signals()
                + self.agent.needs_engine.get_drive_signals()
            )
            self_awareness = self.agent.self_model.get_self_awareness_signal()
            if self_awareness:
                internal_signals.append(self_awareness)
            strategy_signal = self.agent.meta_cognition.consume_strategy_signal()
            if strategy_signal:
                internal_signals.append(strategy_signal)
            protocol_ingress = self.agent.drain_cognitive_ingress()
            for stimulus in protocol_ingress:
                self.agent.psychology.workspace.add_stimulus(stimulus)
            external_signals = self.agent.psychology.workspace.drain_stimuli()

            all_signals = internal_signals + external_signals
            conscious_focus = self.agent.psychology.workspace.select_focus(all_signals)
            if conscious_focus:
                logger.info(f"[Loop] Conscious focus: {[getattr(s, 'content', str(s)) for s in conscious_focus]}")
                self.agent.memory_system.working.add_focus(conscious_focus)
            if any(getattr(s, 'source', '') == "Physiology" and getattr(s, 'content', '') == "Hunger" for s in conscious_focus):
                self.agent.psychology.emotion.update_from_event({"type": "low_energy_warning"})

            modulators = self.agent.psychology.emotion.get_decision_modulators()
            thought = self.agent.thinking_system.reasoning.reason(
                focus=conscious_focus,
                context=self.agent.memory_system.working.get_context()
            )
            plan = self.agent.thinking_system.reasoning.formulate_plan(
                focus=conscious_focus,
                world_model=self.agent.world_model,
            )
            logger.info(f"[Loop] Thought: {thought.content}")
            if plan["goal"]:
                logger.info(f"[Loop] Plan goal: {plan['goal']}")

            social_focus = any(
                s.source in {"Sociology", "SocialMind"} or ("social" in s.content.lower())
                for s in conscious_focus
            )
            if social_focus:
                partners = self.agent.sociology.manager.find_partners(capability="collaboration")
                collab_action = self.agent.sociology.social_mind.propose_collaboration(
                    goal={"name": plan["goal"] or "social_task"},
                    potential_partners=partners,
                    manager=self.agent.sociology.manager,
                )
                if collab_action.get("action") == "send_message":
                    self.agent.outbound_action_queue.put_nowait(
                        Action(
                            name="send_message",
                            params={
                                "recipient": collab_action["recipient"],
                                "content": collab_action["content"],
                                "intent": "task.propose",
                                "metadata": {"goal": plan["goal"] or "social_task"},
                            },
                            reason="propose collaboration",
                        )
                    )
                    logger.info(f"[Loop] Collaboration proposal sent to {collab_action['recipient']}")

            action = self.agent.action_system.decision.choose_action(
                conscious_focus,
                world_model=self.agent.world_model,
                self_model=self.agent.self_model,
                sociology=self.agent.sociology,
                emotional_modulation=modulators,
            )

            if action:
                logger.info(f"[Loop] Decided to execute action: {action.name}")
                if action.name == "send_message":
                    self.agent.outbound_action_queue.put_nowait(action)
                elif action.name == "respond_to_message":
                    source = action.params.get("source", "")
                    content = action.params.get("content", "")
                    
                    # Generate response using LLM if available
                    if hasattr(self.agent.action_system.decision, "generate_response"):
                        # We need to run this async method in the sync loop
                        # Create a new event loop for this sync thread to run the async LLM call
                        try:
                            # Use a new event loop since this is running in a dedicated thread
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            response_text = loop.run_until_complete(
                                self.agent.action_system.decision.generate_response(content, source)
                            )
                            loop.close()
                        except Exception as e:
                            import traceback
                            logger.error(f"Error generating LLM response:\n{traceback.format_exc()}")
                            response_text = f"[Auto response to: {content}] Error calling LLM: {str(e)}"
                    else:
                        response_text = f"[Auto response to: {content}] This is a placeholder response. LLM integration needed."
                        
                    recipient = action.params.get("recipient", "")
                    response_action = Action(
                        name="send_message",
                        params={
                            "recipient": recipient,
                            "content": response_text
                        },
                        reason="Respond to message via slow path"
                    )
                    self.agent.outbound_action_queue.put_nowait(response_action)
                    logger.info(f"[Loop] Put send_message action to queue: recipient={recipient}, content_length={len(response_text)}")
                else:
                    outcome = self.agent.action_system.executor.execute(action)
                    logger.info(f"[Loop] Internal action outcome: {outcome}")
                    self.agent.psychology.emotion.update_from_event(outcome)
                    self.agent.self_model.update_from_experience(outcome)
                    self.agent.world_model.update_from_reality(action, outcome)
                    self.agent.memory_system.episodic.store_experience(
                        event=action.reason,
                        emotions=self.agent.psychology.emotion.state,
                        outcome=outcome
                    )
                    if self.agent.prompt_evolution is not None:
                        self.agent.prompt_evolution.ingest_runtime_outcome(
                            action_status=outcome.get("status", ""),
                            turn_count=1,
                        )
                    self.agent.meta_cognition.review_last_decision(
                        thought=thought,
                        action=action,
                        outcome=outcome
                    )
                    if outcome.get("type") == "interaction":
                        self.agent.sociology.social_mind.model_other_agent(outcome)

            if self.agent.physiology.lifecycle.age_ticks % 10 == 0:
                logger.info(f"[Loop] Agent '{self.agent.id}' is reflecting on its experiences...")
                reflection = self.agent.reflection_system.reflect()
                if reflection:
                    logger.info(f"[Loop] Reflection summary: {reflection}")
            if self.agent.prompt_evolution is not None and self.agent.physiology.lifecycle.age_ticks % 20 == 0:
                decisions = self.agent.prompt_evolution.auto_decide_deployments(
                    min_samples=12,
                    promote_success_rate=0.78,
                    promote_error_rate=0.2,
                    rollback_error_rate=0.45,
                )
                if decisions:
                    logger.info(f"[Loop] Prompt evolution auto decisions: {decisions}")

            time.sleep(TICK_INTERVAL)

        logger.info(f"[Loop] Agent '{self.agent.id}' life loop has stopped.")

    def stop(self):
        """Signals the loop to stop."""
        self._stop_event.set()
