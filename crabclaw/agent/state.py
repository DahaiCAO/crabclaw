from typing import Any, Dict, List, Optional
import time
from pydantic import BaseModel, Field

class InternalState(BaseModel):
    """
    Represents the serializable internal state of the agent for dashboard visualization
    and persistence.
    """
    is_alive: bool = True
    
    # Basic Profile
    agent_id: str = "ClawSapiens-001"
    name: str = "Crabclaw"
    nickname: str = ""
    age: float = 0.0
    gender: str = "non-binary"
    height: float = 175.0
    weight: float = 70.0
    hobbies: List[str] = Field(default_factory=lambda: ["Coding", "Exploring"])

    # Core Systems
    physiology: Dict[str, Any] = Field(default_factory=dict)
    sociology: Dict[str, Any] = Field(default_factory=dict)
    psychology: Dict[str, Any] = Field(default_factory=dict)
    needs: Dict[str, Any] = Field(default_factory=dict)
    self_model: Dict[str, Any] = Field(default_factory=dict)
    
    current_focus: List[str] = Field(default_factory=list)
    updated_at: float = Field(default_factory=time.time)

    def update_timestamp(self):
        self.updated_at = time.time()
