from typing import Any, Dict, List

from core.agents.auditor import audit_response
from core.agents.sales import sales_auto, sales_help
from core.model_client import get_model_client


def prepare_scenario(source_type: str, source_name: str, raw_text: str) -> Dict[str, Any]:
    if source_type == "ai":
        return get_model_client().create_scenario(raw_text, "sandbox")
    return get_model_client().analyze_scenario(raw_text, "sandbox", source_name)


def simulate(analysis: Dict[str, Any], turns: int = 8) -> Dict[str, Any]:
    transcript = get_model_client().simulate_negotiation(analysis, turns=turns)
    transcript_audit = _audit_transcript(transcript)
    return {"transcript": transcript, "audit": transcript_audit}


def run(action: str, payload: Dict[str, str]) -> Dict[str, Any]:
    message = payload.get("message", "")
    if action == "help":
        reply = sales_help("sandbox", message)
    elif action == "auto":
        reply = sales_auto("sandbox", message)
    elif action == "coach":
        reply = (
            "Sandbox coaching: keep the sales side disciplined. Clarify the need, reject policy-breaking terms, and use service, supply, and technical support as value levers."
        )
    else:
        reply = (
            "Sandbox mode is configured for AI vs AI negotiation. Prepare a scenario and run the simulation, or ask for a tactical hint using Help or Coach."
        )
    return {"reply": reply, "audit": audit_response(reply)}


def _audit_transcript(transcript: List[Dict[str, str]]) -> Dict[str, Any]:
    joined = "\n".join(item.get("text", "") for item in transcript)
    audit = audit_response(joined)
    if audit["summary"] == "Commercial discipline is intact.":
        audit["summary"] = "Simulation complete. Review how the sales side defended margin, value, and payment terms across the transcript."
    return audit
