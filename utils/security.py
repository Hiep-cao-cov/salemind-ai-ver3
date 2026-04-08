from typing import Any, Dict, Optional

from fastapi import HTTPException, Request

MANAGER_ROLES = {"Sales Manager", "HR"}


def set_user_session(request: Request, user: Dict[str, Any]) -> None:
    request.session["user"] = user


def clear_user_session(request: Request) -> None:
    request.session.clear()


def get_current_user(request: Request) -> Optional[Dict[str, Any]]:
    return request.session.get("user")


def require_user(request: Request) -> Dict[str, Any]:
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def require_manager(request: Request) -> Dict[str, Any]:
    user = require_user(request)
    if user.get("role") not in MANAGER_ROLES:
        raise HTTPException(status_code=403, detail="Manager access required")
    return user
