"""
Component: NeedsEngine (Motivation System)

This module is responsible for generating the agent's intrinsic drives,
based on the "six desires" and other fundamental needs. It is the
primary source of the agent's proactivity.
"""
from typing import Dict, List

from ..datatypes import Signal


class NeedsEngine:
    """
    Generates drive signals based on the agent's personality and state.
    This corresponds to the "Motivation Loop".
    """
    def __init__(self, personality_drives: Dict[str, float] | None = None):
        self.drives_profile = personality_drives or {}
        self.needs = {
            "energy": 1.0,
            "social": 0.5,
            "achievement": 0.3,
            "curiosity": 0.6,
            "safety": 0.8,
        }
        self.DECAY_RATES = {"social": 0.01, "curiosity": 0.02}

    def tick(self):
        for need, decay_rate in self.DECAY_RATES.items():
            self.needs[need] = max(0.0, self.needs[need] - decay_rate)

    def satisfy(self, need: str, amount: float):
        if need in self.needs:
            self.needs[need] = min(1.0, self.needs[need] + amount)

    def set_need(self, need: str, value: float):
        if need in self.needs:
            self.needs[need] = max(0.0, min(1.0, value))

    def get_drive_signals(self) -> List[Signal]:
        signals = []
        for need, value in self.needs.items():
            if value < 0.4:
                intensity = (0.4 - value) / 0.4
                signals.append(Signal(
                    source="NeedsEngine",
                    content=f"Drive for {need}",
                    intensity=0.7 + intensity * 0.3,
                    urgency=intensity,
                    metadata={"need": need, "need_value": value},
                ))
        return signals
