"""
HABOS Architecture - Main Scheduler

This module defines the BehaviorScheduler, which is the top-level controller of the entire system.
It is responsible for initializing and running the three major engines (reactive, proactive, reflection) simultaneously,
and managing shared resources and state persistence.
"""
import asyncio
import logging
import signal
from pathlib import Path

from crabclaw.agent.loop import AgentLoop  # Reactive engine
from crabclaw.bus.queue import MessageBus
from crabclaw.channels.manager import ChannelManager
from crabclaw.config.loader import get_data_dir
from crabclaw.config.schema import Config
from crabclaw.cron.service import CronService
from crabclaw.cron.types import CronJob
from crabclaw.heartbeat.service import HeartbeatService
from crabclaw.providers.base import LLMProvider
from crabclaw.prompts.manager import PromptManager
from crabclaw.proactive.engine import ProactiveEngine  # Proactive engine
from crabclaw.proactive.state import InternalState
from crabclaw.reflection.engine import ReflectionEngine  # Reflection engine
from crabclaw.reflection.logger import AuditLogger
from crabclaw.session.manager import SessionManager
from crabclaw.agent.tools.registry import ToolRegistry
from crabclaw.dashboard.broadcaster import DashboardBroadcaster
from crabclaw.dashboard.server import DashboardServer
from crabclaw.dashboard.server import DashboardConfig as _DashboardConfig
from crabclaw.dashboard.tailer import JsonlTailer
from crabclaw.gateway.server import GatewayServer, GatewayServerConfig
from crabclaw.i18n.translator import detect_system_language, set_language

logger = logging.getLogger(__name__)


class BehaviorScheduler:
    """
    Behavior Scheduler.
    """

    def __init__(self, config: Config):
        self.config = config
        lang = getattr(config, "language", None) or detect_system_language()
        set_language(lang)
        self.workspace = config.workspace_path
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.state_file = self.workspace / "internal_state.json"
        self.audit_log_file = self.workspace / "audit.log.jsonl"
        self.prompts_dir = self.workspace / "prompts"

        # 1. Initialize shared resources
        self.state = self._load_internal_state()
        self.bus = MessageBus()
        self.provider = self._init_provider()
        self.audit_logger = AuditLogger(str(self.audit_log_file), on_event=self._on_audit_event)
        self.session_manager = SessionManager(self.workspace)
        self.prompt_manager = PromptManager(self.prompts_dir)
        self.tool_registry = ToolRegistry()
        self.dashboard_broadcaster = DashboardBroadcaster()
        self._audit_tailer: JsonlTailer | None = None
        self._state_ticker: asyncio.Task | None = None

        # 3. Initialize peripheral services
        self.cron_service = self._init_cron_service()
        self.channel_manager = ChannelManager(self.config, self.bus)
        self.gateway_server = self._init_gateway_server()
        self.dashboard_server = self._init_dashboard_server()

        # 4. Initialize the three major engines
        self.reactive_engine = self._init_reactive_engine()
        self.proactive_engine = self._init_proactive_engine()
        self.reflection_engine = self._init_reflection_engine()
        
        # 5. Initialize heartbeat service (depends on reactive engine)
        self.heartbeat_service = self._init_heartbeat_service()

        # 6. Establish callback dependencies between services
        self._setup_callbacks()

        self._tasks = []

    def _init_gateway_server(self) -> GatewayServer:
        cfg = GatewayServerConfig(
            enabled=True,
            host=self.config.gateway.host,
            port=self.config.gateway.port,
        )
        return GatewayServer(cfg)

    def _init_dashboard_server(self) -> DashboardServer:
        static_dir = Path(__file__).parent.parent / "dashboard" / "static"
        cfg = _DashboardConfig(
            enabled=self.config.dashboard.enabled,
            host=self.config.gateway.host,
            http_port=self.config.dashboard.http_port,
            ws_port=self.config.dashboard.ws_port,
        )
        return DashboardServer(self.dashboard_broadcaster, static_dir=static_dir, config=cfg)

    async def _start_dashboard_streams(self) -> None:
        # 1) Tail audit log file (helps after restarts / external writers).
        if self.config.dashboard.audit_tail_enabled:
            self._audit_tailer = JsonlTailer(
                path=self.audit_log_file,
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
                await self.dashboard_broadcaster.publish("internal_state", self.state.model_dump())
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
                self.dashboard_broadcaster.publish("audit", entry)
            )
        except RuntimeError:
            # No loop yet (early init); ignore.
            return

    def _init_provider(self) -> LLMProvider:
        from crabclaw.providers.custom_provider import CustomProvider
        from crabclaw.providers.litellm_provider import LiteLLMProvider
        from crabclaw.providers.openai_codex_provider import OpenAICodexProvider

        model = self.config.agents.defaults.model
        provider_name = self.config.get_provider_name(model) or "custom"
        p = self.config.get_provider(model)

        if provider_name == "openai_codex" or model.startswith("openai-codex/"):
            return OpenAICodexProvider(default_model=model)

        if provider_name == "custom":
            return CustomProvider(
                api_key=p.api_key if p else "no-key",
                api_base=self.config.get_api_base(model) or "http://localhost:8000/v1",
                default_model=model,
            )

        return LiteLLMProvider(
            api_key=p.api_key if p else None,
            api_base=self.config.get_api_base(model),
            default_model=model,
            extra_headers=p.extra_headers if p else None,
            provider_name=provider_name,
        )

    def _init_cron_service(self) -> CronService:
        cron_store_path = get_data_dir() / "cron" / "jobs.json"
        return CronService(cron_store_path)

    def _init_reactive_engine(self) -> AgentLoop:
        return AgentLoop(
            bus=self.bus,
            provider=self.provider,
            workspace=self.workspace,
            model=self.config.agents.defaults.model,
            temperature=self.config.agents.defaults.temperature,
            max_tokens=self.config.agents.defaults.max_tokens,
            max_iterations=self.config.agents.defaults.max_tool_iterations,
            memory_window=self.config.agents.defaults.memory_window,
            reasoning_effort=self.config.agents.defaults.reasoning_effort,
            brave_api_key=self.config.tools.web.search.api_key or None,
            web_proxy=self.config.tools.web.proxy or None,
            exec_config=self.config.tools.exec,
            cron_service=self.cron_service,
            restrict_to_workspace=self.config.tools.restrict_to_workspace,
            session_manager=self.session_manager,
            audit_logger=self.audit_logger,
            internal_state=self.state,
            prompt_manager=self.prompt_manager,
            tool_registry=self.tool_registry,
            mcp_servers=self.config.tools.mcp_servers,
            channels_config=self.config.channels,
        )

    def _init_proactive_engine(self) -> ProactiveEngine:
        return ProactiveEngine(
            state=self.state,
            bus=self.bus,
            provider=self.provider,
            prompt_manager=self.prompt_manager,
            tool_registry=self.tool_registry,
        )

    def _init_reflection_engine(self) -> ReflectionEngine:
        return ReflectionEngine(
            state=self.state,
            provider=self.provider,
            audit_log_path=str(self.audit_log_file),
            prompt_manager=self.prompt_manager,
            on_event=self._on_reflection_event,
        )

    def _on_reflection_event(self, event: dict) -> None:
        try:
            asyncio.get_running_loop().create_task(
                self.dashboard_broadcaster.publish("reflection", event)
            )
        except RuntimeError:
            return

    def _init_heartbeat_service(self) -> HeartbeatService:
        hb_cfg = self.config.gateway.heartbeat
        return HeartbeatService(
            workspace=self.workspace,
            provider=self.provider,
            model=self.reactive_engine.model,
            on_execute=self._on_heartbeat_execute,
            on_notify=self._on_heartbeat_notify,
            interval_s=hb_cfg.interval_s,
            enabled=hb_cfg.enabled,
        )

    def _setup_callbacks(self):
        """Set up callback functions between services."""
        self.cron_service.on_job = self._on_cron_job

    async def _on_cron_job(self, job: CronJob) -> str | None:
        """Execute a cron job."""
        # This logic is directly migrated from the old cli/commands.py
        from crabclaw.agent.tools.cron import CronTool
        from crabclaw.agent.tools.message import MessageTool
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
            if ":" not in key: continue
            channel, chat_id = key.split(":", 1)
            if channel in {"cli", "system"}: continue
            if channel in enabled and chat_id:
                return channel, chat_id
        return "cli", "direct"

    async def _on_heartbeat_execute(self, tasks: str) -> str:
        """Execute heartbeat tasks through the reactive engine."""
        channel, chat_id = self._pick_heartbeat_target()
        return await self.reactive_engine.process_direct(
            tasks, session_key="heartbeat", channel=channel, chat_id=chat_id
        )

    async def _on_heartbeat_notify(self, response: str) -> None:
        """Send heartbeat response to user channel."""
        from crabclaw.bus.events import OutboundMessage
        channel, chat_id = self._pick_heartbeat_target()
        if channel != "cli":
            await self.bus.publish_outbound(OutboundMessage(channel=channel, chat_id=chat_id, content=response))

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
                self.dashboard_broadcaster.publish("internal_state", self.state.model_dump())
            )
        except RuntimeError:
            pass

    async def run(self):
        """
        Start all engines and services simultaneously and manage their lifecycle.
        """
        logger.info("Behavior Scheduler starting all services and engines...")

        # Start peripheral services
        await self.gateway_server.start()
        await self.dashboard_server.start()
        await self._start_dashboard_streams()
        await self.cron_service.start()
        await self.heartbeat_service.start()
        
        # Start background tasks for the three major engines (if enabled in config)
        if self.config.proactive.enabled:
            self.proactive_engine.start(interval_seconds=self.config.proactive.interval)
        if self.config.reflection.enabled:
            self.reflection_engine.start(interval_seconds=self.config.reflection.interval)
        
        # Start the core reactive engine and channel manager
        reactive_task = asyncio.create_task(self.reactive_engine.run())
        channels_task = asyncio.create_task(self.channel_manager.start_all())
        self._tasks.extend([reactive_task, channels_task])

        logger.info("All services and engines are now running.")
        logger.info("Dashboard: {}", self.dashboard_server.http_url)

        # Gracefully handle stop signals
        loop = asyncio.get_running_loop()
        stop_signals = []
        for name in ("SIGHUP", "SIGINT", "SIGTERM"):
            if hasattr(signal, name):
                stop_signals.append(getattr(signal, name))
        for s in stop_signals:
            try:
                loop.add_signal_handler(s, lambda s=s: asyncio.create_task(self.stop()))
            except (NotImplementedError, RuntimeError):
                # Windows / embedded loops may not support signal handlers.
                pass

        # Wait for core tasks to complete and periodically save state
        try:
            core_tasks = self._tasks
            while all(not task.done() for task in core_tasks):
                done, pending = await asyncio.wait(
                    core_tasks,
                    return_when=asyncio.FIRST_COMPLETED,
                    timeout=self.config.scheduler.save_interval,
                )

                if not done:
                    # Timeout occurred, save state and continue loop
                    self._save_internal_state()
                else:
                    # A task finished, break the loop to shut down
                    for task in done:
                        if task.exception():
                            logger.error(f"Core task failed, initiating shutdown: {task}", exc_info=task.exception())
                        else:
                            logger.info(f"Core task finished, initiating shutdown: {task}")
                    break
        except asyncio.CancelledError:
            logger.info("Scheduler main loop was cancelled.")

    async def stop(self):
        logger.info("Behavior Scheduler stopping all services and engines...")
        
        # Stop all background tasks and engines
        self.proactive_engine.stop()
        self.reflection_engine.stop()
        self.heartbeat_service.stop()
        self.cron_service.stop()
        
        self.reactive_engine.stop()
        
        await self.channel_manager.stop_all()
        await self.reactive_engine.close_mcp()
        await self._stop_dashboard_streams()
        await self.dashboard_server.stop()
        await self.gateway_server.stop()

        for task in self._tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)

        self._save_internal_state()
        logger.info("Behavior Scheduler stopped gracefully.")
