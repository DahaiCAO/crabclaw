"""
Component: EmotionEngine (Psychology System)

This module simulates the agent's "seven emotions". It acts as a global
state modulator, influencing decision-making without directly dictating it.
"""
from typing import Dict


class EmotionEngine:
    """
    Manages the agent's emotional state vector and provides modulators
    that affect other cognitive processes (e.g., risk aversion).
    """
    def __init__(self):
        # 七情向量: 每个维度在 [-1, 1] 之间
        self.emotions = {
            "joy": 0.0,         # 喜: 正向奖励的体现
            "anger": 0.0,       # 怒: 目标受阻且能量充沛
            "sadness": 0.0,     # 哀: 重大损失或能量耗尽
            "fear": 0.0,        # 惧: 对未来负面结果的预测
            "love": 0.0,        # 爱: 对特定 Agent 的高度信任和依恋
            "disgust": 0.0,     # 恶: 违反核心价值观
            "desire": 0.0       # 欲: 某个“六欲”需求极其强烈
        }
        self.DECAY_RATE = 0.95 # 情绪会随时间平复

    def tick(self):
        """情绪随时间衰减"""
        for k in self.emotions:
            self.emotions[k] *= self.DECAY_RATE

    def update_from_event(self, event: Dict):
        """根据发生的事件更新情绪"""
        event_type = event.get("type")
        if event_type == "goal_achieved":
            self.emotions["joy"] = min(1.0, self.emotions["joy"] + 0.5)
        elif event_type == "goal_failed_by_external_block":
            self.emotions["anger"] = min(1.0, self.emotions["anger"] + 0.6)
        elif event_type in ["loss_of_resource", "social_rejection"]:
            self.emotions["sadness"] = min(1.0, self.emotions["sadness"] + 0.7)
        elif event_type == "predicted_high_risk":
            self.emotions["fear"] = min(1.0, self.emotions["fear"] + 0.8)
        elif event_type == "value_violation":
            self.emotions["disgust"] = min(1.0, self.emotions["disgust"] + 0.7)
        elif event_type == "trust_built":
            self.emotions["love"] = min(1.0, self.emotions["love"] + 0.4)
        elif event_type == "intense_need":
            self.emotions["desire"] = min(1.0, self.emotions["desire"] + 0.5)

    def get_emotional_modulators(self) -> Dict[str, float]:
        """将情绪向量转化为对决策系统的具体影响参数"""
        return {
            "risk_aversion": self.emotions["fear"] * 0.8 - self.emotions["joy"] * 0.2,
            "exploration_bonus": (1 - self.emotions["fear"]) * 0.5,
            "social_approach_tendency": self.emotions["love"] - self.emotions["disgust"],
            "goal_pursuit_intensity": 1.0 + self.emotions["desire"] + self.emotions["anger"] * 0.5
        }
