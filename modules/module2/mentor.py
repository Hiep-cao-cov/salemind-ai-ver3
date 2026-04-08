from typing import Any, Dict

from core.agents.auditor import audit_response
from core.agents.sales import sales_help, sales_response


def run(action: str, payload: Dict[str, str]) -> Dict[str, Any]:
    message = payload.get("message", "")
    context_text = payload.get("context_text", "")
    if action == "help":
        reply = sales_help("mentor", message, context_text)
    elif action == "coach":
        reply = (
            "Mentor insight: first uncover the real decision driver, then anchor on value and risk. Keep your stance commercially firm without sounding rigid."
        )
    else:
        reply = sales_response("mentor", message, context_text)
    audit = audit_response(reply)
    audit["summary"] = f"Mentor note: {audit['summary']}"
    return {"reply": reply, "audit": audit}
