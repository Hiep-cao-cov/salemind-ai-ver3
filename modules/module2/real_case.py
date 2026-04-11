from typing import Any, Dict

from core.agents.auditor import audit_response
from core.agents.sales import sales_help, sales_response
from core.model_client import get_model_client
from core.prompts.buyer_prompt import build_buyer_prompt


def prepare_scenario(
    source_type: str,
    source_name: str,
    raw_text: str,
    *,
    use_llm: bool = True,
) -> Dict[str, Any]:
    return get_model_client().analyze_scenario(raw_text, "real_case", source_name, use_llm=use_llm)


def _normalize_role(payload: Dict[str, str]) -> str:
    role = str(payload.get("practice_role", "") or "").strip().lower()
    return role if role in ("buyer", "seller") else "buyer"


def run(action: str, payload: Dict[str, str]) -> Dict[str, Any]:
    message = payload.get("message", "")
    context_text = payload.get("context_text", "")
    practice_role = _normalize_role(payload)

    if not context_text.strip():
        reply = "Please upload or paste case material first so the model can summarize it and extract negotiation context."
        return {"reply": reply, "audit": audit_response(reply)}

    if practice_role == "seller":
        if action == "help":
            reply = (
                "Buyer-side hint: anchor on a concrete case fact, cite competitive or timeline pressure, "
                "and ask the seller to justify price with delivery, service, or risk — not discounts first."
            )
        elif action == "coach":
            reply = (
                "Buyer coaching: challenge vague claims, probe implementation and supply risk, "
                "and keep payment discipline (you want shorter terms, not longer)."
            )
        else:
            prompt = build_buyer_prompt("real_case", message, context_text=context_text)
            reply = get_model_client().complete(prompt)
        return {"reply": reply, "audit": audit_response(reply)}

    if action == "help":
        reply = sales_help("real_case", message, context_text)
    elif action == "coach":
        reply = "Real Case coaching: stay grounded in the uploaded material. Use only facts supported by the case and convert them into negotiation leverage."
    else:
        reply = sales_response("real_case", message, context_text)
    return {"reply": reply, "audit": audit_response(reply)}
