"""
HABOS Architecture - Main Scheduler

This module defines the BehaviorScheduler, which is the top-level controller of the entire system.
It is responsible for initializing and running the three major engines (reactive, proactive, reflection) simultaneously,
and managing shared resources and state persistence.
"""
import asyncio
import hashlib
import json
import logging
import signal
import time
from pathlib import Path
from typing import TYPE_CHECKING

from crabclaw.agent.state import InternalState
from crabclaw.agent.tools.registry import ToolRegistry
from crabclaw.bus.broadcaster import BroadcastManager
from crabclaw.bus.queue import MessageBus
from crabclaw.channels.manager import ChannelManager
from crabclaw.config.loader import get_data_dir
from crabclaw.config.schema import Config
from crabclaw.cron.service import CronService
from crabclaw.cron.types import CronJob
from crabclaw.dashboard.server import DashboardConfig as _DashboardConfig
from crabclaw.dashboard.server import DashboardServer
from crabclaw.dashboard.tailer import JsonlTailer
from crabclaw.gateway.server import GatewayServer, GatewayServerConfig
from crabclaw.i18n.translator import detect_system_language, set_language
from crabclaw.providers.base import LLMProvider
from crabclaw.session.manager import SessionManager
from crabclaw.templates.manager import PromptManager
from crabclaw.user.manager import UserManager
from crabclaw.utils.audit_logger import SecureAuditLogger

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from crabclaw.agent.loop import IOProcessor
    from crabclaw.sapiens.agent import AgentSapiens


class BehaviorScheduler:
    """
    Behavior Scheduler.
    """

    def __init__(self, config: Config, sapiens_core: "AgentSapiens", enable_gateway: bool = True, enable_dashboard: bool = True):
        self.config = config
        self.sapiens_core = sapiens_core
        self.enable_gateway = enable_gateway
        self.enable_dashboard = enable_dashboard
        lang = getattr(config, "language", None) or detect_system_language()
        set_language(lang)
        self.workspace = config.workspace_path
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.state_file = self.workspace / "internal_state.json"
        self.audit_log_dir = self.workspace / "audit"
        self.prompts_dir = self.workspace / "prompts"

        # 1. Initialize shared resources
        self.state = self._load_internal_state()
        self.bus = MessageBus()
        self.provider = self._init_provider()
        self.audit_logger = SecureAuditLogger(str(self.audit_log_dir))
        self.session_manager = SessionManager(self.workspace)
        self.prompt_manager = PromptManager(self.prompts_dir)
        self.tool_registry = ToolRegistry()
        self.broadcast_manager = BroadcastManager()
        self.user_manager = UserManager(self.workspace)
        self._audit_tailer: JsonlTailer | None = None
        self._state_ticker: asyncio.Task | None = None

        # 3. Initialize peripheral services
        self.cron_service = self._init_cron_service()
        self.channel_manager = ChannelManager(self.config, self.bus)
        self.gateway_server = self._init_gateway_server() if enable_gateway else None
        self.dashboard_server = self._init_dashboard_server() if enable_dashboard else None

        # 4. Initialize the three major engines
        self.reactive_engine = self._init_reactive_engine()

        # 7. Establish callback dependencies between services
        self._setup_callbacks()

        # 8. Start prompt evolution background task
        self._evolution_task: asyncio.Task | None = None

        self._tasks = []

    @staticmethod
    def _stable_event_id(prefix: str, payload: dict) -> str:
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
        return f"{prefix}-{digest}"

    def _init_gateway_server(self) -> "GatewayServer":
        from crabclaw.gateway.server import GatewayServer
        cfg = GatewayServerConfig(
            enabled=True,
            host=self.config.gateway.host,
            port=self.config.gateway.port,
        )
        gateway_server = GatewayServer(
            cfg,
            bus=self.bus,
            broadcast_manager=self.broadcast_manager,
            workspace=self.workspace,
        )
        return gateway_server

    def _init_dashboard_server(self) -> DashboardServer:
        static_dir = Path(__file__).parent.parent / "dashboard" / "static"
        cfg = _DashboardConfig(
            enabled=self.config.dashboard.enabled,
            host=self.config.gateway.host,
            http_port=self.config.dashboard.http_port,
            ws_port=self.config.dashboard.ws_port,
        )
        return DashboardServer(
            self.broadcast_manager,
            static_dir=static_dir,
            config=cfg,
            workspace=self.workspace,
        )

    async def _start_dashboard_streams(self) -> None:
        # 1) Tail audit log file (helps after restarts / external writers).
        if self.config.dashboard.audit_tail_enabled:
            self._audit_tailer = JsonlTailer(
                path=self.audit_log_dir,
                broadcaster=self.dashboard_broadcaster,
                event_type="audit",
                from_end=self.config.dashboard.audit_tail_from_end,
                poll_interval_s=0.5,
            )
            await self._audit_tailer.start()

        # 2) Push InternalState periodically so UI is "live".
        interval = max(0.2, float(self.config.dashboard.state_push_interval_s))

        async def _tick():
            while True:
                # Sync state from sapiens_core if available
                if self.sapiens_core:
                    self.state.is_alive = self.sapiens_core.is_alive
                    self.state.agent_id = self.sapiens_core.id

                    # Sync Profile (Placeholder for name, etc. if they exist in core)
                    if hasattr(self.sapiens_core, "self_model") and self.sapiens_core.self_model:
                        self.state.name = self.sapiens_core.self_model.identity.get("name") or "Crabclaw"
                        self.state.nickname = self.sapiens_core.self_model.identity.get("nickname") or ""
                        self.state.gender = self.sapiens_core.self_model.identity.get("gender") or "non-binary"
                        self.state.height = self.sapiens_core.self_model.identity.get("height") or 175.0
                        self.state.weight = self.sapiens_core.self_model.identity.get("weight") or 70.0
                        self.state.hobbies = self.sapiens_core.self_model.identity.get("hobbies") or []
                        self.state.self_model = {
                            "confidence": self.sapiens_core.self_model.state.get("confidence", 0.0),
                            "skills": self.sapiens_core.self_model.identity.get("skills", {})
                        }

                    # Sync Physiology
                    if hasattr(self.sapiens_core, "physiology") and self.sapiens_core.physiology:
                        p = self.sapiens_core.physiology
                        if hasattr(p, "metabolism"):
                            self.state.physiology = {
                                "metabolism": {
                                    "energy": getattr(p.metabolism, "energy", 0.0),
                                    "health": getattr(p.metabolism, "health", 0.0),
                                    "satiety": getattr(p.metabolism, "satiety", 0.0),
                                }
                            }
                        if hasattr(p, "lifecycle"):
                            self.state.age = p.lifecycle.age
                            self.state.physiology["plasticity"] = p.lifecycle.plasticity

                    # Sync Sociology
                    if hasattr(self.sapiens_core, "sociology") and self.sapiens_core.sociology:
                        s = self.sapiens_core.sociology
                        known_count = len(getattr(s.social_mind, "mind_models", {}))
                        potential_count = getattr(s.manager, "get_potential_agents_count", lambda: 0)()

                        self.state.sociology = {
                            "economy": {
                                "credits": getattr(s.economy, "credits", 0.0)
                            },
                            "ticks_since_last_interaction": getattr(s.manager, "ticks_since_last_interaction", 0),
                            "partners_count": max(known_count, potential_count)
                        }

                    # Sync Psychology
                    if hasattr(self.sapiens_core, "psychology") and self.sapiens_core.psychology:
                        psy = self.sapiens_core.psychology
                        if hasattr(psy, "emotion"):
                            self.state.psychology = {
                                "emotion": psy.emotion.state
                            }

                    # Sync Needs
                    if hasattr(self.sapiens_core, "needs_engine") and self.sapiens_core.needs_engine:
                        self.state.needs = self.sapiens_core.needs_engine.needs

                    self.state.update_timestamp()

                await self.broadcast_manager.publish("internal_state", self.state.model_dump())
                await asyncio.sleep(interval)

        self._state_ticker = asyncio.create_task(_tick())

    async def _stop_dashboard_streams(self) -> None:
        if self._state_ticker:
            self._state_ticker.cancel()
            try:
                await self._state_ticker
            except BaseException:
                pass
            self._state_ticker = None
        if self._audit_tailer:
            await self._audit_tailer.stop()
            self._audit_tailer = None

    def _on_audit_event(self, entry: dict) -> None:
        # AuditLogger callback is sync; fan-out async without blocking.
        try:
            asyncio.get_running_loop().create_task(
                self.broadcast_manager.publish("audit", entry)
            )
        except Exception:
            pass

    async def _on_settings_updated(self, payload: dict) -> None:
        """Handle settings updates from the dashboard."""
        logger.info(f"Applying settings update to core: {payload}")

        # 1. Update Core Identity if possible
        if self.sapiens_core and self.sapiens_core.self_model:
            identity = self.sapiens_core.self_model.identity
            if "agent_name" in payload:
                identity["name"] = payload["agent_name"]
            if "nickname" in payload:
                identity["nickname"] = payload["nickname"]
            if "gender" in payload:
                identity["gender"] = payload["gender"]
            if "age" in payload:
                val = float(payload["age"])
                identity["age"] = val
                # Re-calculate age_ticks based on new age so simulation continues from here
                if hasattr(self.sapiens_core, "physiology") and self.sapiens_core.physiology:
                    p = self.sapiens_core.physiology
                    if hasattr(p, "lifecycle"):
                        p.lifecycle.age_ticks = int(val * p.lifecycle.TICK_PER_YEAR)
            if "height" in payload:
                identity["height"] = float(payload["height"])
            if "weight" in payload:
                identity["weight"] = float(payload["weight"])
            if "hobbies" in payload:
                hobbies = payload["hobbies"]
                if isinstance(hobbies, str):
                    hobbies = [h.strip() for h in hobbies.split(",") if h.strip()]
                identity["hobbies"] = hobbies

        # 2. Update Psychology/Emotion in core if available
        if self.sapiens_core and self.sapiens_core.psychology and self.sapiens_core.psychology.emotion:
            emotion = self.sapiens_core.psychology.emotion.state
            if "psychology.curiosity" in payload:
                emotion["curiosity"] = float(payload["psychology.curiosity"])
            if "psychology.confidence" in payload:
                emotion["confidence"] = float(payload["psychology.confidence"])
            if "psychology.risk_aversion" in payload:
                emotion["risk_aversion"] = float(payload["psychology.risk_aversion"])
            if "psychology.social_trust" in payload:
                emotion["social_trust"] = float(payload["psychology.social_trust"])

        # 3. Update local state immediately to avoid lag
        if "agent_name" in payload:
            self.state.name = payload["agent_name"]
        if "nickname" in payload:
            self.state.nickname = payload["nickname"]

        # Force a state push
        await self.broadcast_manager.publish(
                        scope="system:state",
                        message={"type": "internal_state", "data": self.state.model_dump()}
                    )

    def _init_provider(self) -> LLMProvider:
        provider = self.config.create_llm_provider_for_callpoint("agent", allow_missing=True)
        if provider is not None:
            return provider

        from crabclaw.providers.custom_provider import CustomProvider
        from crabclaw.providers.litellm_provider import LiteLLMProvider
        from crabclaw.providers.openai_codex_provider import OpenAICodexProvider

        # Don't use self.config.agents.defaults.model, use provider-specific models
        # Try to find a provider with api_key configured
        from crabclaw.providers.registry import PROVIDERS
        for spec in PROVIDERS:
            p = getattr(self.config.providers, spec.name, None)
            if p and hasattr(p, 'api_key') and p.api_key:
                model = getattr(p, 'model', '')
                if model:
                    provider_name = spec.name
                    if provider_name == "openai_codex" or model.startswith("openai-codex/"):
                        return OpenAICodexProvider(default_model=model)
                    if provider_name == "custom":
                        return CustomProvider(
                            api_key=p.api_key,
                            api_base=getattr(p, 'api_base', None) or "http://localhost:8000/v1",
                            default_model=model,
                        )
                    return LiteLLMProvider(
                        api_key=p.api_key,
                        api_base=getattr(p, 'api_base', None),
                        default_model=model,
                        extra_headers=getattr(p, 'extra_headers', None),
                        provider_name=provider_name,
                    )
        return None

    def _init_cron_service(self) -> CronService:
        cron_store_path = get_data_dir() / "cron" / "jobs.json"
        return CronService(cron_store_path)

    def _init_reactive_engine(self) -> "IOProcessor":
        from crabclaw.agent.loop import IOProcessor
        return IOProcessor(
            bus=self.bus,
            sapiens_core=self.sapiens_core,
            broadcast_manager=self.broadcast_manager
        )


    def _setup_callbacks(self) -> None:
        """Setup all event bus listeners and cross-service callbacks."""
        self.bus.subscribe("settings_updated", self._on_settings_updated)
        self.bus.subscribe("inbound", self._on_bus_inbound)
        self.bus.subscribe("outbound", self._on_bus_outbound)
        self.cron_service.on_job = self._on_cron_job

        # Set up prompt manager change callback for hot-reload notifications
        self.prompt_manager.add_change_callback(self._on_prompt_changed)

    def _on_prompt_changed(self, template_name: str, new_content: str):
        """Callback when a prompt template is changed.

        Args:
            template_name: Name of the changed template.
            new_content: New content of the template.
        """
        logger.info("Prompt template '%s' changed, broadcasting to dashboard", template_name)
        try:
            # Broadcast to dashboard
            asyncio.get_running_loop().create_task(
                self.dashboard_broadcaster.publish("template_reloaded", {
                    "template_name": template_name,
                    "file_name": f"{template_name.upper()}.md",
                    "message": f"Template '{template_name.upper()}.md' has been hot-reloaded",
                    "timestamp": time.time()
                })
            )
        except RuntimeError:
            # No event loop running, ignore
            pass

    async def _on_bus_inbound(self, msg) -> None:
        metadata = msg.metadata or {}
        scope = metadata.get("user_id")
        if not scope:
            scope = self.user_manager.resolve_user_by_identity(msg.channel, msg.sender_id)
        if not scope:
            scope = self.user_manager.resolve_user_by_identity(msg.channel, msg.chat_id)
        if not scope:
            return
        event = {
            "type": "inbound_message",
            "channel": msg.channel,
            "chat_id": msg.chat_id,
            "sender_id": msg.sender_id,
            "content": msg.content,
            "timestamp": msg.timestamp.timestamp(),
            "metadata": metadata,
        }
        event["event_id"] = metadata.get("event_id") or self._stable_event_id(
            "in",
            {
                "channel": msg.channel,
                "chat_id": msg.chat_id,
                "sender_id": msg.sender_id,
                "content": msg.content,
                "request_id": metadata.get("request_id", ""),
                "timestamp": event["timestamp"],
            },
        )
        await self.broadcast_manager.publish(scope=scope, message=event)

    async def _on_bus_outbound(self, msg) -> None:
        metadata = msg.metadata or {}
        scope = metadata.get("scope") or metadata.get("user_id") or metadata.get("scope_user_id")
        if not scope:
            scope = self.user_manager.resolve_user_by_identity(msg.channel, msg.chat_id)
        if not scope:
            return
        event = {
            "type": "outbound_message",
            "channel": msg.channel,
            "chat_id": msg.chat_id,
            "content": msg.content,
            "timestamp": time.time(),
            "metadata": metadata,
        }
        event["event_id"] = metadata.get("event_id") or self._stable_event_id(
            "out",
            {
                "channel": msg.channel,
                "chat_id": msg.chat_id,
                "content": msg.content,
                "request_id": metadata.get("request_id", ""),
                "timestamp": event["timestamp"],
            },
        )
        await self.broadcast_manager.publish(scope=scope, message=event)
        await self.broadcast_manager.publish(
            scope=scope,
            message={
                "type": "agent_reply",
                "content": msg.content,
                "channel": msg.channel,
                "chat_id": msg.chat_id,
                "timestamp": time.time(),
                "request_id": metadata.get("request_id", ""),
                "metadata": metadata,
                "event_id": event["event_id"],
            },
        )

    async def _on_cron_job(self, job: CronJob) -> str | None:
        """Execute a cron job."""
        # This logic is directly migrated from the old cli/commands.py
        from crabclaw.agent.tools.cron import CronTool
        reminder_note = (
            f"[Scheduled Task] Timer finished.\n\n"
            f"Task '{job.name}' has been triggered.\n"
            f"Scheduled instruction: {job.payload.message}"
        )

        cron_tool = self.reactive_engine.tools.get("cron")
        cron_token = None
        if isinstance(cron_tool, CronTool):
            cron_token = cron_tool.set_cron_context(True)
        try:
            response = await self.reactive_engine.process_direct(
                reminder_note,
                session_key=f"cron:{job.id}",
                channel=job.payload.channel or "cli",
                chat_id=job.payload.to or "direct",
            )
        finally:
            if isinstance(cron_tool, CronTool) and cron_token is not None:
                cron_tool.reset_cron_context(cron_token)

        # ... (Other callback logic can be migrated as needed)
        return response

    def _pick_heartbeat_target(self) -> tuple[str, str]:
        """Select a routable target for heartbeat messages."""
        enabled = set(self.channel_manager.enabled_channels)
        for item in self.session_manager.list_sessions():
            key = item.get("key") or ""
            if ":" not in key:
                continue
            channel, chat_id = key.split(":", 1)
            if channel in {"cli", "system"}:
                continue
            if channel in enabled and chat_id:
                return channel, chat_id
        return "cli", "direct"


    def _load_internal_state(self) -> InternalState:
        if self.state_file.exists():
            logger.info(f"Loading internal state from {self.state_file}")
            return InternalState.model_validate_json(self.state_file.read_text(encoding="utf-8"))
        logger.info("No internal state file found, creating new one.")
        return InternalState()

    def _save_internal_state(self):
        logger.info(f"Saving internal state to {self.state_file}")
        self.state.update_timestamp()
        self.state_file.write_text(self.state.model_dump_json(indent=2), encoding="utf-8")
        try:
            asyncio.get_running_loop().create_task(
                self.broadcast_manager.publish(
                        scope="system:state",
                        message={"type": "internal_state", "data": self.state.model_dump()}
                    )
            )
        except RuntimeError:
            pass

    async def run(self):
        """
        Start all engines and services simultaneously and manage their lifecycle.
        """
        logger.info("Behavior Scheduler starting all services and engines...")

        # Start peripheral services
        if self.enable_gateway and self.gateway_server:
            try:
                await self.gateway_server.start()
                self.gateway_server._loop = asyncio.get_running_loop()
            except Exception as e:
                logger.warning(f"Gateway server failed to start: {e}")

        if self.enable_dashboard and self.dashboard_server:
            try:
                await self.dashboard_server.start()
                await self._start_dashboard_streams()
            except Exception as e:
                logger.warning(f"Dashboard failed to start: {e}")

        try:
            await self.cron_service.start()
        except Exception as e:
            logger.warning(f"Cron service failed to start: {e}")

        # Start the Sapiens mind thread (it's sync and blocking)
        import threading
        mind_thread = threading.Thread(
            target=self.sapiens_core.live,
            name="sapiens-mind",
            daemon=True
        )
        mind_thread.start()
        logger.info("Sapiens mind thread started.")

        # Start the core reactive engine and channel manager
        reactive_task = asyncio.create_task(self.reactive_engine.run())
        channels_task = asyncio.create_task(self.channel_manager.start_all())
        self._tasks.extend([reactive_task, channels_task])

        logger.info("All services and engines are now running.")
        if self.enable_dashboard and self.dashboard_server:
            logger.info("Dashboard: %s", self.dashboard_server.http_url)

        # Gracefully handle stop signals
        loop = asyncio.get_running_loop()
        
        # We need a robust stop event to avoid double-stopping
        self._stop_event = asyncio.Event()
        
        stop_signals = []
        for name in ("SIGHUP", "SIGINT", "SIGTERM"):
            if hasattr(signal, name):
                stop_signals.append(getattr(signal, name))
        for s in stop_signals:
            try:
                loop.add_signal_handler(s, lambda: asyncio.create_task(self.stop()))
            except (NotImplementedError, RuntimeError):
                # Windows / embedded loops may not support signal handlers.
                pass

        # Wait for core tasks to complete and periodically save state
        try:
            core_tasks = self._tasks
            while all(not task.done() for task in core_tasks) and not self._stop_event.is_set():
                done, pending = await asyncio.wait(
                    core_tasks + [asyncio.create_task(self._stop_event.wait())],
                    return_when=asyncio.FIRST_COMPLETED,
                    timeout=self.config.scheduler.save_interval,
                )

                if not done:
                    # Timeout occurred, save state and continue loop
                    self._save_internal_state()
                else:
                    # Check if we were woken up by the stop event
                    if self._stop_event.is_set():
                        break
                        
                    # A task finished, break the loop to shut down
                    for task in done:
                        # Skip the stop_event.wait() task
                        if getattr(task.get_coro(), "cr_code", None) and "wait" in str(task.get_coro().cr_code):
                            continue
                            
                        if not task.cancelled() and task.exception():
                            logger.error(f"Core task failed, initiating shutdown: {task}", exc_info=task.exception())
                        else:
                            logger.info(f"Core task finished, initiating shutdown: {task}")
                    break
        except asyncio.CancelledError:
            logger.info("Scheduler main loop was cancelled.")
        finally:
            if not self._stop_event.is_set():
                await self.stop()

    async def _run_prompt_evolution(self):
        """Background task for continuous prompt evolution."""
        while True:
            try:
                await asyncio.sleep(1800)  # Run every 30 minutes
                logger.info("Running prompt evolution analysis...")

                records = await self.prompt_evolution.analyze_and_evolve()

                if records:
                    logger.info("Applied %s prompt improvements", len(records))
                    # Broadcast evolution event to dashboard
                    for record in records:
                        try:
                            asyncio.get_running_loop().create_task(
                                self.dashboard_broadcaster.publish("prompt_evolution", {
                                    "template_name": record.template_name,
                                    "change_type": record.change_type,
                                    "rationale": record.rationale,
                                    "expected_improvement": record.expected_improvement,
                                    "timestamp": record.timestamp.isoformat()
                                })
                            )
                        except RuntimeError:
                            pass
                else:
                    logger.debug("No prompt improvements needed at this time")

            except asyncio.CancelledError:
                logger.info("Prompt evolution task was cancelled")
                break
            except Exception as e:
                logger.error("Error in prompt evolution task: %s", e)
                await asyncio.sleep(300)  # Wait 5 minutes before retrying

    async def stop(self):
        if getattr(self, "_stopping", False):
            return
        self._stopping = True
        
        if hasattr(self, "_stop_event"):
            self._stop_event.set()
            
        logger.info("Behavior Scheduler stopping all services and engines...")

        # Cancel prompt evolution task
        if self._evolution_task:
            self._evolution_task.cancel()
            try:
                await self._evolution_task
            except asyncio.CancelledError:
                pass

        # Stop all background tasks and engines
        self.cron_service.stop()

        # Stop reactive engine (IOProcessor)
        if hasattr(self.reactive_engine, "stop"):
            if asyncio.iscoroutinefunction(self.reactive_engine.stop):
                await self.reactive_engine.stop()
            else:
                self.reactive_engine.stop()

        await self.channel_manager.stop_all()

        if self.enable_dashboard and self.dashboard_server:
            await self._stop_dashboard_streams()
            await self.dashboard_server.stop()

        if self.enable_gateway and self.gateway_server:
            await self.gateway_server.stop()

        for task in self._tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)

        self._save_internal_state()
        logger.info("Behavior Scheduler stopped gracefully.")
