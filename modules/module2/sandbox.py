from typing import Any, Dict, List, Optional

from core.agents.auditor import audit_response
from core.agents.sales import sales_auto, sales_help, sales_response
from core.model_client import get_model_client
from core.prompt_loader import get_deal_rule_text


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
    """Run full DEMO simulation using two-agent state internals."""
    turns_total = max(16, min(20, int(turns)))
    state = init_simulation_state(analysis)
    transcript: List[Dict[str, str]] = []
    final_audit: Optional[Dict[str, Any]] = None

    for _ in range(turns_total):
        step = simulate_step(
            analysis,
            simulation_state=state,
            turns=turns_total,
            mentor=False,
        )
        state = step["simulation_state"]
        item = step.get("item")
        if item:
            transcript.append({"role": item.get("role", ""), "text": item.get("text", "")})
        if step.get("done"):
            final_audit = step.get("audit")
            break

    if not final_audit:
        final_audit = _audit_transcript(transcript)
    return {"transcript": transcript, "audit": final_audit, "simulation_state": state}


def init_simulation_state(analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Create a fresh two-agent state for DEMO simulation."""
    return {
        "public_transcript": [],
        "next_speaker": "buyer",
        "buyer_private_context": _build_buyer_private_context(analysis),
        "seller_private_context": _build_seller_private_context(analysis),
        "termination": {"status": "ongoing", "reason": "", "matched_rule": ""},
    }


def _build_buyer_private_context(analysis: Dict[str, Any]) -> Dict[str, Any]:
    risks = [str(x) for x in (analysis.get("risks") or [])[:4]]
    points = [str(x) for x in (analysis.get("negotiation_points") or [])]
    lower_points = " ".join(points).lower()
    goals = [
        "Lower effective total cost versus current quote.",
        "Increase commercial flexibility without losing supply continuity.",
    ]
    if "payment" in lower_points or "days" in lower_points:
        goals.append("Push for longer payment terms where possible.")
    if "compet" in lower_points:
        goals.append("Use competitor offers as leverage.")
    limits = [
        "Do not commit to volume or term without reciprocal concessions.",
        "Keep options open with alternate suppliers.",
    ]
    private_notes = " | ".join(risks[:2]) if risks else "Internal approval pressure on commercial terms."
    return {"goals": goals[:4], "limits": limits[:4], "private_notes": private_notes}


def _build_seller_private_context(analysis: Dict[str, Any]) -> Dict[str, Any]:
    strategies = [str(x) for x in (analysis.get("recommended_strategies") or [])[:4]]
    notes = strategies[0] if strategies else "Defend value through supply reliability and technical support."
    return {
        "goals": [
            "Protect margin and avoid unstructured discounting.",
            "Convert buyer pressure into value-based trade-offs.",
            "Preserve payment discipline at 45 days maximum.",
        ],
        "limits": [
            "Maximum payment term is 45 days.",
            "No rebate-first concessions.",
            "No price reduction without value exchange.",
        ],
        "private_notes": notes,
    }


def legacy_api_hist_to_transcript(api_hist: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Convert legacy user/assistant sim history to shared public transcript."""
    out: List[Dict[str, str]] = []
    for idx in range(1, len(api_hist), 2):
        speaker = "buyer" if (idx // 2) % 2 == 0 else "seller"
        out.append({"speaker": speaker, "text": str(api_hist[idx].get("content", ""))})
    return out


def transcript_to_legacy_api_hist(transcript: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Convert public transcript into compatibility api_hist payload."""
    hist: List[Dict[str, str]] = []
    for item in transcript:
        text = str(item.get("text", ""))
        hist.append({"role": "user", "content": text})
        hist.append({"role": "assistant", "content": text})
    return hist


def _coerce_simulation_state(
    analysis: Dict[str, Any],
    simulation_state: Optional[Dict[str, Any]],
    legacy_api_hist: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    if simulation_state and isinstance(simulation_state, dict):
        state = {
            "public_transcript": list(simulation_state.get("public_transcript") or []),
            "next_speaker": str(simulation_state.get("next_speaker") or "buyer").lower(),
            "buyer_private_context": dict(simulation_state.get("buyer_private_context") or {}),
            "seller_private_context": dict(simulation_state.get("seller_private_context") or {}),
            "termination": dict(simulation_state.get("termination") or {}),
        }
        if state["next_speaker"] not in ("buyer", "seller"):
            state["next_speaker"] = "buyer"
        if not state["buyer_private_context"]:
            state["buyer_private_context"] = _build_buyer_private_context(analysis)
        if not state["seller_private_context"]:
            state["seller_private_context"] = _build_seller_private_context(analysis)
        if not state["termination"]:
            state["termination"] = {"status": "ongoing", "reason": "", "matched_rule": ""}
        return state
    state = init_simulation_state(analysis)
    if legacy_api_hist:
        state["public_transcript"] = legacy_api_hist_to_transcript(legacy_api_hist)
        state["next_speaker"] = "buyer" if len(state["public_transcript"]) % 2 == 0 else "seller"
    return state


def _parse_rule_deal_text(rule_text: str) -> Dict[str, Any]:
    sections: Dict[str, List[str]] = {
        "deal_closed": [],
        "no_deal": [],
        "escalate": [],
    }
    min_turn_for_close = 6
    current = ""

    for raw in str(rule_text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            key = line[1:-1].strip().lower()
            current = key if key in sections else ""
            continue
        if ":" in line and current == "":
            left, right = line.split(":", 1)
            if left.strip().lower() == "min_turn_for_close":
                try:
                    min_turn_for_close = max(1, int(right.strip()))
                except Exception:
                    min_turn_for_close = 6
            continue
        if line.startswith("-"):
            line = line[1:].strip()
        if current and line:
            sections[current].append(line.lower())

    return {
        "min_turn_for_close": min_turn_for_close,
        "deal_closed": sections["deal_closed"],
        "no_deal": sections["no_deal"],
        "escalate": sections["escalate"],
    }


def _evaluate_termination(public_transcript: List[Dict[str, str]], turns_done: int, turns_total: int) -> Dict[str, str]:
    try:
        rule_text = get_deal_rule_text()
    except Exception:
        rule_text = ""
    cfg = _parse_rule_deal_text(rule_text)

    last_text = str(public_transcript[-1].get("text", "") if public_transcript else "").lower()

    def _match_any(candidates: List[str]) -> str:
        for phrase in candidates:
            p = str(phrase or "").strip().lower()
            if p and p in last_text:
                return p
        return ""

    no_deal_hit = _match_any(cfg["no_deal"])
    if no_deal_hit:
        return {"status": "no_deal", "reason": "matched no_deal rule", "matched_rule": no_deal_hit}

    if turns_done >= int(cfg["min_turn_for_close"]):
        deal_hit = _match_any(cfg["deal_closed"])
        if deal_hit:
            return {"status": "deal_closed", "reason": "matched deal_closed rule", "matched_rule": deal_hit}

    if turns_done >= turns_total:
        return {"status": "max_turns", "reason": "reached maximum turns", "matched_rule": ""}

    return {"status": "ongoing", "reason": "", "matched_rule": ""}


def _speaker_label_demo(role: str) -> str:
    if role in ("buyer", "buyer_ai"):
        return "Buyer (AI)"
    if role in ("seller", "sales_ai"):
        return "Covestro sales (AI)"
    return role or "Speaker"


def _mentor_prior_dialogue(transcript: List[Dict[str, str]], *, max_lines: int = 8) -> str:
    if len(transcript) <= 1:
        return ""
    prior = transcript[:-1][-max_lines:]
    lines: List[str] = []
    for item in prior:
        r = item.get("speaker", "")
        label = "Buyer" if r == "buyer" else "Covestro sales"
        lines.append(f"{label}: {item.get('text', '').strip()}")
    return "\n".join(lines)


def _mentor_insight_for_turn(
    analysis: Dict[str, Any],
    item: Dict[str, str],
    public_transcript: List[Dict[str, str]],
) -> str:
    recent = _mentor_prior_dialogue(public_transcript)
    label = _speaker_label_demo(item.get("role", ""))
    utterance = str(item.get("text") or "")
    return get_model_client().mentor_analyze_demo_turn(
        speaker_label=label,
        utterance=utterance,
        analysis=analysis,
        recent_dialogue=recent,
    )


def simulate_buyer_step(analysis: Dict[str, Any], simulation_state: Dict[str, Any]) -> Dict[str, str]:
    """Generate one buyer utterance and mutate simulation_state."""
    text = get_model_client().generate_buyer_line(analysis, simulation_state)
    item = {"role": "buyer_ai", "text": text}
    simulation_state["public_transcript"].append({"speaker": "buyer", "text": text})
    simulation_state["next_speaker"] = "seller"
    return item


def simulate_seller_step(analysis: Dict[str, Any], simulation_state: Dict[str, Any]) -> Dict[str, str]:
    """Generate one seller utterance and mutate simulation_state."""
    text = get_model_client().generate_seller_line(analysis, simulation_state)
    item = {"role": "sales_ai", "text": text}
    simulation_state["public_transcript"].append({"speaker": "seller", "text": text})
    simulation_state["next_speaker"] = "buyer"
    return item


def simulate_step(
    analysis: Dict[str, Any],
    api_hist: Optional[List[Dict[str, Any]]] = None,
    *,
    simulation_state: Optional[Dict[str, Any]] = None,
    turns: int = 18,
    mentor: bool = True,
) -> Dict[str, Any]:
    """Run one DEMO turn using two-agent state; keep legacy api_hist compatibility."""
    api_hist = api_hist or []
    state = _coerce_simulation_state(analysis, simulation_state, api_hist)
    public_transcript = list(state.get("public_transcript") or [])
    turns_total = max(16, min(20, int(turns)))
    turns_done = len(public_transcript)
    termination = dict(state.get("termination") or {"status": "ongoing", "reason": "", "matched_rule": ""})

    if termination.get("status") not in ("", "ongoing"):
        return {
            "ok": True,
            "done": True,
            "simulation_state": state,
            "api_hist": transcript_to_legacy_api_hist(public_transcript),
            "item": None,
            "audit": None,
            "mentor_insight": None,
            "turns_total": turns_total,
            "turns_done": turns_done,
            "termination": termination,
        }

    if turns_done >= turns_total:
        termination = {"status": "max_turns", "reason": "reached maximum turns", "matched_rule": ""}
        state["termination"] = termination
        return {
            "ok": True,
            "done": True,
            "simulation_state": state,
            "api_hist": transcript_to_legacy_api_hist(public_transcript),
            "item": None,
            "audit": None,
            "mentor_insight": None,
            "turns_total": turns_total,
            "turns_done": turns_done,
            "termination": termination,
        }

    next_speaker = str(state.get("next_speaker") or "buyer")
    if next_speaker == "seller":
        item = simulate_seller_step(analysis, state)
    else:
        item = simulate_buyer_step(analysis, state)

    public_transcript = list(state.get("public_transcript") or [])
    turns_done = len(public_transcript)
    termination = _evaluate_termination(public_transcript, turns_done, turns_total)
    state["termination"] = termination
    done = termination.get("status") != "ongoing"

    audit = None
    if done:
        ui_transcript = [{"role": ("buyer_ai" if t.get("speaker") == "buyer" else "sales_ai"), "text": t.get("text", "")} for t in public_transcript]
        audit = _audit_transcript(ui_transcript)

    mentor_insight: Optional[str] = None
    if mentor:
        mentor_insight = _mentor_insight_for_turn(analysis, item, public_transcript)

    return {
        "ok": True,
        "done": done,
        "simulation_state": state,
        "api_hist": transcript_to_legacy_api_hist(public_transcript),
        "item": item,
        "audit": audit,
        "mentor_insight": mentor_insight,
        "turns_total": turns_total,
        "turns_done": turns_done,
        "termination": termination,
    }


def run(action: str, payload: Dict[str, str]) -> Dict[str, Any]:
    message = payload.get("message", "")
    context_text = payload.get("context_text", "")
    if action == "help":
        reply = sales_help("sandbox", message)
    elif action == "auto":
        reply = sales_auto("sandbox", message)
    elif action == "coach":
        reply = (
            "Sandbox coaching: keep the sales side disciplined. Clarify the need, reject policy-breaking terms, and use service, supply, and technical support as value levers."
        )
    else:
        # DEMO chat: user negotiates directly with Seller AI.
        reply = sales_response("sandbox", message, context_text)
    return {"reply": reply, "audit": audit_response(reply)}


def _audit_transcript(transcript: List[Dict[str, str]]) -> Dict[str, Any]:
    joined = "\n".join(item.get("text", "") for item in transcript)
    audit = audit_response(joined)
    if audit["summary"] == "Commercial discipline is intact.":
        audit["summary"] = "Simulation complete. Review how the sales side defended margin, value, and payment terms across the transcript."
    return audit
