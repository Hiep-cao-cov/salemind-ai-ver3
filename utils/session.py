from typing import Dict, Any

from utils.db import create_session, get_session_detail, list_recent_sessions_for_user


def bootstrap_user_session(user_id: int, module_key: str = "module_2", mode_key: str = "sandbox") -> str:
    return create_session(user_id=user_id, module_key=module_key, mode_key=mode_key, title="New negotiation session")


def get_user_session_overview(user_id: int, mode_key: str | None = None) -> Dict[str, Any]:
    recent_sessions = list_recent_sessions_for_user(user_id, mode_key=mode_key, limit=10)
    return {"recent_sessions": recent_sessions}


def get_session_snapshot(session_id: str) -> Dict[str, Any]:
    return get_session_detail(session_id)
