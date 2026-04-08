from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ModeContext:
    source_type: str = ""
    source_name: str = ""
    raw_text: str = ""
    title: str = ""
    summary: str = ""
    key_points: List[str] = field(default_factory=list)
    negotiation_points: List[str] = field(default_factory=list)
    generated_scenario: str = ""


@dataclass
class AppState:
    session_id: str
    module_key: str = "module_2"
    mode_key: str = "sandbox"
    user_id: Optional[int] = None
    user_name: str = ""
    user_role: str = ""
    turn_count: int = 0
    chat_history: List[Dict[str, str]] = field(default_factory=list)
    context: ModeContext = field(default_factory=ModeContext)
    audit_flags: Dict[str, bool] = field(default_factory=dict)
