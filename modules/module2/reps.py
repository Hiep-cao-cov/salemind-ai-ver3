from typing import Any, Dict

from core.agents.auditor import audit_response
from core.model_client import get_model_client


def prepare_scenario(
    source_type: str,
    source_name: str,
    raw_text: str,
    *,
    use_llm: bool = True,
) -> Dict[str, Any]:
    return get_model_client().analyze_scenario(raw_text, "reps", source_name, use_llm=use_llm)


def run(action: str, payload: Dict[str, str]) -> Dict[str, Any]:
    message = payload.get("message", "")
    context_text = payload.get("context_text", "")
    if not context_text.strip():
        reply = "Select a drill scenario from the scenario library first."
        return {"reply": reply, "audit": audit_response(reply)}
    if action == "help":
        reply = "Fast hint: ask one clarifying question, defend value immediately, and keep your answer tight."
    elif action == "coach":
        reply = "Reps coaching: shorten the response, anchor earlier on value, and do not let competitor pressure drag you into reactive discounting."
    else:
        reply = (
            "Drill feedback: your response should stay sharp, defend margin, protect payment terms, and reframe the conversation to service, supply continuity, and business risk."
            f"\n\nCurrent drill context:\n{context_text[:800]}"
            + (f"\n\nYour latest draft:\n{message}" if message else "")
        )
    return {"reply": reply, "audit": audit_response(reply)}
