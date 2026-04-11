from typing import Any, Dict, List, Optional

from core.agents.auditor import audit_response
from core.agents.sales import sales_auto, sales_help
from core.model_client import get_model_client


def prepare_scenario(
    source_type: str,
    source_name: str,
    raw_text: str,
    *,
    use_llm: bool = True,
) -> Dict[str, Any]:
    if source_type == "ai":
        return get_model_client().create_scenario(raw_text, "sandbox", use_llm=use_llm)
    return get_model_client().analyze_scenario(raw_text, "sandbox", source_name, use_llm=use_llm)


def simulate(analysis: Dict[str, Any], turns: int = 18) -> Dict[str, Any]:
    transcript = get_model_client().simulate_negotiation(analysis, turns=turns)
    transcript_audit = _audit_transcript(transcript)
    return {"transcript": transcript, "audit": transcript_audit}


def transcript_from_api_hist(api_hist: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Rebuild UI transcript roles from chat-style history (user/assistant pairs)."""
    out: List[Dict[str, str]] = []
    for idx in range(1, len(api_hist), 2):
        turn = idx // 2
        role = "buyer_ai" if turn % 2 == 0 else "sales_ai"
        out.append({"role": role, "text": str(api_hist[idx].get("content", ""))})
    return out


def _speaker_label_demo(role: str) -> str:
    if role == "buyer_ai":
        return "Buyer (AI)"
    if role == "sales_ai":
        return "Covestro sales (AI)"
    return role or "Speaker"


def _mentor_prior_dialogue(transcript: List[Dict[str, str]], *, max_lines: int = 8) -> str:
    if len(transcript) <= 1:
        return ""
    prior = transcript[:-1][-max_lines:]
    lines: List[str] = []
    for item in prior:
        r = item.get("role", "")
        label = "Buyer" if r == "buyer_ai" else "Covestro sales"
        lines.append(f"{label}: {item.get('text', '').strip()}")
    return "\n".join(lines)


def _mentor_insight_for_turn(
    analysis: Dict[str, Any],
    item: Dict[str, str],
    api_hist_after_turn: List[Dict[str, Any]],
) -> str:
    transcript = transcript_from_api_hist(api_hist_after_turn)
    recent = _mentor_prior_dialogue(transcript)
    label = _speaker_label_demo(item.get("role", ""))
    utterance = str(item.get("text") or "")
    return get_model_client().mentor_analyze_demo_turn(
        speaker_label=label,
        utterance=utterance,
        analysis=analysis,
        recent_dialogue=recent,
    )


def simulate_step(
    analysis: Dict[str, Any],
    api_hist: List[Dict[str, Any]],
    *,
    turns: int = 18,
    mentor: bool = True,
) -> Dict[str, Any]:
    """
    One simulation turn for step-by-step DEMO. No LLM call when already at max turns.
    """
    client = get_model_client()
    step = client.simulate_negotiation_step(analysis, list(api_hist), max_turns=turns)
    if step is None:
        return {
            "ok": True,
            "done": True,
            "api_hist": api_hist,
            "item": None,
            "audit": None,
            "mentor_insight": None,
            "turns_total": max(16, min(20, int(turns))),
            "turns_done": len(api_hist) // 2,
        }

    audit = None
    if step["done"]:
        audit = _audit_transcript(transcript_from_api_hist(step["api_hist"]))

    mentor_insight: Optional[str] = None
    if mentor and step.get("item"):
        mentor_insight = _mentor_insight_for_turn(analysis, step["item"], step["api_hist"])

    return {
        "ok": True,
        "done": step["done"],
        "api_hist": step["api_hist"],
        "item": step["item"],
        "audit": audit,
        "mentor_insight": mentor_insight,
        "turns_total": max(16, min(20, int(turns))),
        "turns_done": len(step["api_hist"]) // 2,
    }


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
