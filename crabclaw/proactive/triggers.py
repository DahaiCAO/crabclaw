"""
HABOS 架构 - 感知层 (Perception Layer) 的一部分

此模块定义了触发系统 (TriggerSystem)，它负责监测内部状态，
识别需要启动主动行为的条件（如风险、机会、空闲时间等）。
"""
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from crabclaw.proactive.state import InternalState


class TriggerEvent:
    """
    当一个触发条件被满足时，生成的结构化事件对象。
    这是从“感知层”传递给“决策层”的信息。
    """

    def __init__(
        self, trigger_type: str, description: str, metadata: Optional[Dict[str, Any]] = None
    ):
        self.trigger_type = trigger_type
        self.description = description
        self.metadata = metadata or {}

    def __repr__(self):
        return f"TriggerEvent(type='{self.trigger_type}', desc='{self.description}')"


class BaseTrigger(ABC):
    """所有具体触发器的抽象基类 (策略模式)。"""

    @abstractmethod
    def check(self, state: InternalState) -> Optional[TriggerEvent]:
        """
        检查是否满足触发条件。
        如果满足，返回一个 TriggerEvent 对象；否则返回 None。
        """
        pass


# --- 具体触发器实现 ---

class RiskTrigger(BaseTrigger):
    """风险触发器：检查内部状态中记录的各种风险。"""

    def check(self, state: InternalState) -> Optional[TriggerEvent]:
        # 示例：检查用户是否长时间未响应
        if "user_unresponsive" in state.risks:
            risk_data = state.risks["user_unresponsive"]
            days = risk_data.get("days", 0)
            if days >= 3:  # 阈值可以配置
                return TriggerEvent(
                    trigger_type="risk_detected.user_unresponsive",
                    description=f"用户已 {days} 天未在 '{risk_data.get('topic', '一个重要话题')}' 上响应。",
                    metadata=risk_data,
                )
        # 此处可以添加更多风险类型的检查，如“市场数据过期”等
        return None


class GoalUnfinishedTrigger(BaseTrigger):
    """目标未完成触发器：检查是否有正在进行中的任务。"""

    def check(self, state: InternalState) -> Optional[TriggerEvent]:
        in_progress_tasks = [t for t in state.tasks if t.get("status") == "in_progress"]
        if in_progress_tasks:
            return TriggerEvent(
                trigger_type="goal_unfinished",
                description=f"有 {len(in_progress_tasks)} 个正在进行中的任务需要关注。",
                metadata={"tasks": in_progress_tasks},
            )
        return None


class IdleTimeTrigger(BaseTrigger):
    """空闲时间触发器：检查 Agent 是否长时间未进行主动交互。"""

    def __init__(self, idle_seconds: int = 3600 * 24):  # 默认为 24 小时
        self.idle_seconds = idle_seconds

    def check(self, state: InternalState) -> Optional[TriggerEvent]:
        current_time = time.time()
        if (current_time - state.last_proactive_ts) > self.idle_seconds:
            return TriggerEvent(
                trigger_type="long_idle_time",
                description=f"Agent 已超过 {self.idle_seconds / 3600:.1f} 小时未进行主动交互。",
                metadata={"idle_seconds": self.idle_seconds},
            )
        return None


# --- 触发系统管理器 ---

class TriggerSystem:
    """
    管理和运行所有触发器的系统。
    """

    def __init__(self):
        self._triggers: List[BaseTrigger] = []
        self._register_default_triggers()

    def _register_default_triggers(self):
        """注册所有默认的触发器。未来可以从配置动态加载。"""
        self.add_trigger(RiskTrigger())
        self.add_trigger(GoalUnfinishedTrigger())
        self.add_trigger(IdleTimeTrigger(idle_seconds=3600 * 8)) # 缩短时间以便测试

    def add_trigger(self, trigger: BaseTrigger):
        self._triggers.append(trigger)

    def check(self, state: InternalState) -> List[TriggerEvent]:
        """
        运行所有已注册的触发器，并收集所有被触发的事件。
        """
        triggered_events = []
        for trigger in self._triggers:
            event = trigger.check(state)
            if event:
                triggered_events.append(event)
        return triggered_events
