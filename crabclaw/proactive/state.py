"""
HABOS 架构 - 动机层 (Motivation Layer)

此模块定义了 Agent 的内部状态模型 (InternalState)，它是所有主动行为和长期目标的动机来源。
这个模型是 Agent "灵魂"的数据化体现。
"""
import time
from typing import Any, Dict, List

from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    """
    世界模型的一部分：对用户的理解和画像。
    """
    preferences: Dict[str, Any] = Field(
        default_factory=dict,
        description="用户偏好, 例如 {'format': 'structured', 'tone': 'concise'}"
    )
    tolerance: Dict[str, str] = Field(
        default_factory=dict,
        description="用户容忍度, 例如 {'verbosity': 'low'}"
    )
    # 未来可以扩展更多维度，如知识背景、兴趣领域等


class InternalState(BaseModel):
    """
    Agent 的内部状态，驱动所有行为的核心数据结构。
    对应 HABOS 的动机层。
    """
    # 战略层：长期目标
    long_term_goal: str = Field(
        default="成为用户最可信赖的决策伙伴，通过主动洞察和精准分析，帮助用户降低风险、把握机会。",
        description="Agent 的长期存在价值或使命"
    )

    # 战术层：中期任务
    tasks: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="当前正在进行或待处理的中期任务列表, e.g., [{'id': 'task-001', 'desc': '完成A公司的技术调研报告', 'status': 'in_progress'}]"
    )

    # 风险与机会监控
    risks: Dict[str, Any] = Field(
        default_factory=dict,
        description="监控到的潜在风险, e.g., {'user_unresponsive': {'days': 3, 'topic': 'A公司财报'}}"
    )
    opportunities: Dict[str, Any] = Field(
        default_factory=dict,
        description="发现的潜在机会, e.g., {'new_policy_detected': '关于AI行业的新政策'}"
    )

    # 用户模型
    user_profile: UserProfile = Field(
        default_factory=UserProfile,
        description="对当前交互用户的画像"
    )

    # 资源分配器
    interruption_budget: int = Field(
        default=100,
        description="主动打扰用户的预算，每次主动行为会消耗，可随时间恢复或根据用户反馈增减"
    )

    # 状态元数据
    last_update_ts: float = Field(
        default_factory=time.time,
        description="此状态对象最后一次被更新的时间戳"
    )
    last_proactive_ts: float = Field(
        default_factory=time.time,
        description="上一次执行主动行为的时间戳"
    )
    last_reflection_ts: float = Field(
        default_factory=time.time,
        description="上一次执行反思循环的时间戳"
    )
    skill_needs: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="反思引擎识别出的能力短板或新技能需求, e.g., [{'name': 'image_generator', 'description': 'a tool to generate images from text'}]"
    )

    def update_timestamp(self):
        """便捷方法，用于在状态更新时调用。"""
        self.last_update_ts = time.time()

    def get_last_skill_need(self) -> Dict[str, Any] | None:
        """获取最近的一个技能需求。"""
        if self.skill_needs:
            return self.skill_needs[-1]
        return None

    def clear_last_skill_need(self):
        """清除最近的一个技能需求。"""
        if self.skill_needs:
            self.skill_needs.pop()
            self.update_timestamp()
