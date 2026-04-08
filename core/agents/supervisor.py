from typing import Literal

ActionType = Literal["chat", "help", "auto", "coach"]


def resolve_action(action: str, mode: str) -> ActionType:
    normalized = (action or "chat").lower().strip()
    if normalized == "auto" and mode != "sandbox":
        return "chat"
    if normalized in {"chat", "help", "auto", "coach"}:
        return normalized  # type: ignore[return-value]
    return "chat"
