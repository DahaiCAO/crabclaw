"""
HABOS 架构 - 决策层 (Decision Layer) 的主动通道引擎

此模块定义了 ProactiveEngine，它是一个在后台运行的独立服务，
负责驱动 Agent 在没有外部输入时进行自主思考和主动行动。
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

# 配置日志记录器
logger = logging.getLogger(__name__)


class ProactiveEngine:
    """
    主动行为引擎。
    """

    def __init__(
        self,
        state: InternalState,
        bus: MessageBus,
        provider: LLMProvider,
        prompt_manager: PromptManager,
        tool_registry: "ToolRegistry",
        # 未来可以从外部注入，以实现更好的依赖管理
        trigger_system: Optional[TriggerSystem] = None,
        action_library: Optional[ActionLibrary] = None,
        action_selector: Optional[ActionSelector] = None,
    ):
        self.state = state
        self.bus = bus
        self.provider = provider
        self.prompt_manager = prompt_manager
        self.tool_registry = tool_registry

        # 装配三大核心组件
        self.triggers = trigger_system or TriggerSystem()
        self.library = action_library or ActionLibrary()
        self.selector = action_selector or ActionSelector(provider=self.provider, prompt_manager=self.prompt_manager)

        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def run_cycle(self):
        """
        执行一个完整的主动行为“感知-思考-决策-行动”循环。
        """
        logger.debug("Running proactive engine cycle...")

        # 1. 感知层：检查触发条件
        triggered_events = self.triggers.check(self.state)
        if not triggered_events:
            logger.debug("No proactive triggers met.")
            return

        logger.info(f"Proactive triggers met: {triggered_events}")

        # 2. 决策层：选择最佳行动
        best_action = await self.selector.select_action(
            self.state, triggered_events, self.library
        )
        if not best_action:
            logger.info("Action selector decided not to act.")
            return

        logger.info(f"Executing proactive action: {best_action.name}")
        try:
            # 3. 执行层：执行行动
            await best_action.execute(self.state, self.bus, self.provider, self.tool_registry)

            # 4. 动机层更新：更新状态和预算
            self.state.last_proactive_ts = time.time()
            self.state.interruption_budget -= best_action.cost
            self.state.update_timestamp()
            # self.save_state() # 应该由总调度器来负责持久化
            logger.info(
                f"Proactive action '{best_action.name}' executed. "
                f"Interruption budget remaining: {self.state.interruption_budget}"
            )
        except Exception as e:
            logger.error(f"Error executing proactive action '{best_action.name}': {e}", exc_info=True)

    async def _loop(self, interval_seconds: int):
        """
        引擎的主循环，定期运行 run_cycle。
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
                # 避免因单次错误导致整个循环崩溃，等待下一个周期
                await asyncio.sleep(interval_seconds)
        logger.info("Proactive Engine stopped.")

    def start(self, interval_seconds: int = 60):
        """在后台启动主动行为引擎。"""
        if not self._running:
            self._task = asyncio.create_task(self._loop(interval_seconds))

    def stop(self):
        """停止主动行为引擎。"""
        if self._task and not self._task.done():
            self._task.cancel()
