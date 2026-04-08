from typing import Any, Dict

from core.agents.auditor import audit_response
from core.agents.sales import sales_help, sales_response
from core.model_client import get_model_client


def prepare_scenario(source_type: str, source_name: str, raw_text: str) -> Dict[str, Any]:
    return get_model_client().analyze_scenario(raw_text, "real_case", source_name)


def run(action: str, payload: Dict[str, str]) -> Dict[str, Any]:
    message = payload.get("message", "")
    context_text = payload.get("context_text", "")
    if not context_text.strip():
        reply = "Please upload or paste case material first so the model can summarize it and extract negotiation context."
        return {"reply": reply, "audit": audit_response(reply)}
    if action == "help":
        reply = sales_help("real_case", message, context_text)
    elif action == "coach":
        reply = "Real Case coaching: stay grounded in the uploaded material. Use only facts supported by the case and convert them into negotiation leverage."
    else:
        reply = sales_response("real_case", message, context_text)
    return {"reply": reply, "audit": audit_response(reply)}
