"""The Physiology Layer of the HAOS.

This module simulates the agent's physical existence and constraints,
such as energy, health, and lifecycle. It is the source of the most
fundamental survival drives.
"""
from .datatypes import Signal


class MetabolismEngine:
    """
    Manages the agent's vital signs, primarily its energy.
    Energy is consumed over time and through actions, creating a fundamental
    need for resource acquisition.
    """
    def __init__(self, energy_max: float = 100.0, health_max: float = 100.0, satiety_max: float = 100.0):
        # 生命体征 (Vital Signs)
        self.energy_max = energy_max
        self.energy = energy_max
        self.health_max = health_max
        self.health = health_max
        self.satiety_max = satiety_max
        self.satiety = satiety_max  # 对应 Token/Credit 储备

        # 衰减率
        self.TIME_DECAY_RATE = 0.01  # 每 Tick 能量自然流失
        self.ACTION_COST = 0.5       # 每次 LLM 调用的基础成本

    def tick(self):
        """时间流逝导致的基础消耗"""
        self.energy = max(0, self.energy - self.TIME_DECAY_RATE)

    def record_action_cost(self, tokens_used: int):
        """记录动作消耗"""
        cost = self.ACTION_COST + (tokens_used / 1000.0)
        self.energy = max(0, self.energy - cost)
        self.satiety = max(0, self.satiety - cost)  # 消耗储备资源

    def recharge(self, amount: float):
        """Recharges the agent's energy."""
        self.energy = min(self.energy_max, self.energy + amount)
        self.satiety = min(self.satiety_max, self.satiety + amount)
        print(f"[Physiology] Energy recharged. Current energy: {self.energy:.2f}")

    def is_alive(self) -> bool:
        """Checks if the agent has enough energy to continue existing."""
        return self.energy > 0

    def get_homeostatic_drives(self) -> list[Signal]:
        """生成稳态驱动信号 (Homeostatic Drives)"""
        signals = []
        if self.energy < 30:
            intensity = (30 - self.energy) / 30.0
            signals.append(Signal(
                source="Physiology",
                content="Hunger",
                intensity=0.8 + intensity * 0.2, # 强度极高
                urgency=1.0 # 必须立即处理
            ))
        # ...可以添加健康、疲劳等其他信号
        return signals

class LifecycleManager:
    """
    Manages the agent's age and developmental stage.
    This influences properties like learning plasticity.
    """
    def __init__(self):
        self.age_ticks = 0
        self.TICK_PER_YEAR = 365 * 24 * 60 # 假设每分钟一个 Tick

    def tick(self):
        """Increments the agent's age."""
        self.age_ticks += 1

    @property
    def age(self) -> float:
        """Returns the agent's age in "years"."""
        return self.age_ticks / self.TICK_PER_YEAR

    @property
    def plasticity(self) -> float:
        """学习可塑性，随年龄增长而下降"""
        return max(0.1, 1.0 - (self.age / 10.0)) # 假设10年完全固化

class PhysiologySystem:
    """
    A container for all physiological components.
    """
    def __init__(self):
        self.metabolism = MetabolismEngine()
        self.lifecycle = LifecycleManager()

    def tick(self):
        """A single tick of the physiological clock."""
        self.metabolism.tick()
        self.lifecycle.tick()

    def get_signals(self) -> list[Signal]:
        """Gathers all signals from the physiological layer."""
        return self.metabolism.get_homeostatic_drives()
