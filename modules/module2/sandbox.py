from functools import lru_cache
from types import MappingProxyType
from typing import Any, Dict, List, Optional

from core.agents.auditor import audit_response
from core.agents.sales import sales_auto, sales_help, sales_response
from core.model_client import get_model_client
from core.prompt_loader import (
    get_buy_skill_text,
    get_deal_rule_text,
    get_sell_skill_text,
)
from utils.ai_output_config import clamp_demo_turns, get_int


@lru_cache(maxsize=1)
def _config_store() -> Dict[str, Any]:
    """Phase 0 immutable config store loaded once per process."""
    cfg = {
        "sell_skill": get_sell_skill_text(),
        "buy_skill": get_buy_skill_text(),
    }
    return MappingProxyType(cfg)  # type: ignore[return-value]


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
    """Run full DEMO simulation using Demo_AI_negotiation scripted transcript (replay per step)."""
    turns_total = clamp_demo_turns(int(turns))
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
    """Create a fresh shared-memory state for DEMO simulation."""
    _ = _config_store()
    return {
        "session_meta": {
            "turn_number": 0,
            "current_agent": "buyer",
            "status": "ongoing",
            "max_turns": 20,
            "deadlock_counter": 0,
            "difficulty": "medium",
        },
        "public_transcript": [],
        "history": [],
        "agreed_points": [],
        "open_issues": [],
        "coaching_recs": {"for_seller": "", "for_buyer": ""},
        "deadlock_risk": "LOW",
        "next_speaker": "buyer",
        "buyer_private_context": _build_buyer_private_context(analysis),
        "seller_private_context": _build_seller_private_context(analysis),
        "termination": {"status": "ongoing", "reason": "", "matched_rule": ""},
        "demo_script": [],
        "demo_script_cursor": 0,
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
    return {
        "goals": goals[:4],
        "limits": limits[:4],
        "private_notes": private_notes,
        "coaching_advice_prev": "",
    }


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
        "coaching_advice_prev": "",
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
            "session_meta": dict(simulation_state.get("session_meta") or {}),
            "public_transcript": list(simulation_state.get("public_transcript") or []),
            "history": list(simulation_state.get("history") or []),
            "agreed_points": list(simulation_state.get("agreed_points") or []),
            "open_issues": list(simulation_state.get("open_issues") or []),
            "coaching_recs": dict(simulation_state.get("coaching_recs") or {}),
            "deadlock_risk": str(simulation_state.get("deadlock_risk") or "LOW"),
            "next_speaker": str(simulation_state.get("next_speaker") or "buyer").lower(),
            "buyer_private_context": dict(simulation_state.get("buyer_private_context") or {}),
            "seller_private_context": dict(simulation_state.get("seller_private_context") or {}),
            "termination": dict(simulation_state.get("termination") or {}),
            "demo_script": list(simulation_state.get("demo_script") or []),
            "demo_script_cursor": int(simulation_state.get("demo_script_cursor") or 0),
        }
        if state["next_speaker"] not in ("buyer", "seller"):
            state["next_speaker"] = "buyer"
        if not state["buyer_private_context"]:
            state["buyer_private_context"] = _build_buyer_private_context(analysis)
        if not state["seller_private_context"]:
            state["seller_private_context"] = _build_seller_private_context(analysis)
        if not state["termination"]:
            state["termination"] = {"status": "ongoing", "reason": "", "matched_rule": ""}
        if not state["session_meta"]:
            state["session_meta"] = {
                "turn_number": len(state["public_transcript"]),
                "current_agent": state["next_speaker"],
                "status": "ongoing",
                "max_turns": 20,
                "deadlock_counter": 0,
            }
        if not state["coaching_recs"]:
            state["coaching_recs"] = {"for_seller": "", "for_buyer": ""}
        if not state["agreed_points"]:
            state["agreed_points"] = []
        if not state["history"]:
            state["history"] = []
        if not state["open_issues"]:
            state["open_issues"] = []
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


def _all_key_terms_agreed(state: Dict[str, Any]) -> bool:
    difficulty = str((state.get("session_meta") or {}).get("difficulty") or "medium").lower()
    def _has_explicit_close(text: str) -> bool:
        lower = (text or "").lower()
        return any(
            p in lower
            for p in (
                "we have a deal",
                "agreement reached",
                "deal confirmed",
                "let's proceed with this deal",
            )
        )

    history = state.get("history") or []
    if len(history) >= 6:
        recent = " ".join(str(x.get("final_output", "")) for x in history[-2:])
        if _has_explicit_close(recent):
            return True

    agreed = [str(x).strip().lower() for x in (state.get("agreed_points") or []) if str(x).strip()]
    required_categories = 3
    if difficulty == "simple":
        required_categories = 2
    elif difficulty == "hard":
        required_categories = 4
    if len(agreed) < required_categories:
        return False
    categories = set()
    for item in agreed:
        if "price" in item or "discount" in item:
            categories.add("price")
        if "payment" in item or "days" in item:
            categories.add("payment")
        if "deliver" in item or "lead time" in item:
            categories.add("delivery")
        if "quantity" in item or "volume" in item:
            categories.add("quantity")
        if "contract" in item or "term" in item:
            categories.add("contract")
    return len(categories) >= required_categories


def _withdrawal_detected(last_text: str) -> bool:
    lower = (last_text or "").lower()
    return any(p in lower for p in ("withdraw", "walk away", "cannot proceed", "terminate negotiation"))


def _check_stopping_condition(state: Dict[str, Any]) -> Dict[str, str]:
    meta = state.get("session_meta") or {}
    difficulty = str(meta.get("difficulty") or "medium").lower()
    if _all_key_terms_agreed(state):
        return {"status": "AGREEMENT", "reason": "all key terms agreed", "matched_rule": ""}
    deadlock_threshold = 3 if difficulty in {"medium", "hard"} else 4
    if int(meta.get("deadlock_counter") or 0) >= deadlock_threshold:
        return {"status": "DEADLOCK", "reason": "deadlock counter reached threshold", "matched_rule": ""}
    history = state.get("history") or []
    last_output = str(history[-1].get("final_output", "") if history else "")
    if _withdrawal_detected(last_output):
        return {"status": "TERMINATED", "reason": "withdrawal intent detected", "matched_rule": ""}
    if int(meta.get("turn_number") or 0) >= int(meta.get("max_turns") or 20):
        return {"status": "TIMEOUT", "reason": "maximum turns reached", "matched_rule": ""}
    return {"status": "ongoing", "reason": "", "matched_rule": ""}


def _extract_agreed_points(text: str) -> List[str]:
    lower = (text or "").lower()
    hits: List[str] = []
    patterns = (
        "agreed on",
        "we agree on",
        "agreement reached on",
    )
    term_keywords = ("price", "payment", "days", "delivery", "lead time", "quantity", "volume", "contract", "term")
    for p in patterns:
        if p in lower and any(k in lower for k in term_keywords):
            hits.append(text.strip()[:180])
            break
    return hits


def _buyer_confirmation_loop_detected(transcript: List[Dict[str, str]], *, lookback: int = 4) -> bool:
    recent_buyer = [str(t.get("text", "")).lower() for t in transcript[-lookback:] if t.get("speaker") == "buyer"]
    if len(recent_buyer) < 2:
        return False
    patterns = ("confirm", "confirmation", "just to confirm", "can you confirm", "please confirm")
    count = sum(1 for line in recent_buyer if any(p in line for p in patterns))
    return count >= 2


def _termination_summary(termination: Dict[str, str]) -> str:
    status = str(termination.get("status") or "").upper()
    if status == "AGREEMENT":
        return "Negotiation ended with an agreement. Key terms were aligned by both sides."
    if status == "DEADLOCK":
        return "Negotiation ended in deadlock. Positions remained stuck without workable convergence."
    if status == "TIMEOUT":
        return "Negotiation reached the maximum turn limit without a confirmed final agreement."
    if status == "TERMINATED":
        return "Negotiation was terminated due to withdrawal intent from one side."
    return ""


def _speaker_label_demo(role: str) -> str:
    if role in ("buyer", "buyer_ai"):
        return "Buyer (AI)"
    if role in ("seller", "sales_ai"):
        return "Covestro sales (AI)"
    return role or "Speaker"


def _mentor_prior_dialogue(transcript: List[Dict[str, str]], *, max_lines: Optional[int] = None) -> str:
    lim = get_int("demo_mentor", "prior_dialogue_max_lines", 8) if max_lines is None else max_lines
    if len(transcript) <= 1:
        return ""
    prior = transcript[:-1][-lim:]
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
    """Generate one buyer turn (draft->coach->decision->state update)."""
    client = get_model_client()
    buyer_private = simulation_state.setdefault("buyer_private_context", {})
    seller_private = simulation_state.setdefault("seller_private_context", {})
    coaching_recs = simulation_state.setdefault("coaching_recs", {"for_seller": "", "for_buyer": ""})
    history = simulation_state.setdefault("history", [])
    session_meta = simulation_state.setdefault("session_meta", {})
    difficulty = str(session_meta.get("difficulty") or "medium").lower()
    if difficulty == "simple" and _buyer_confirmation_loop_detected(simulation_state.get("public_transcript") or []):
        buyer_private["coaching_advice_prev"] = (
            "Do not repeat confirmation requests for the same point. "
            "If terms are clear, acknowledge alignment and move toward closing."
        )
    turn_num = int(session_meta.get("turn_number") or 0) + 1
    session_meta["turn_number"] = turn_num
    session_meta["current_agent"] = "buyer"

    final_text = ""
    final_review: Dict[str, Any] = {}
    final_draft = ""
    for _ in range(3):
        text = client.generate_buyer_line(analysis, simulation_state)
        final_draft = text
        review = client.evaluate_buyer_draft(analysis, simulation_state, text)
        final_review = review
        final_text = text
        recommendation = str(review.get("recommendation") or "").strip()
        verdict = str(review.get("verdict") or "FAIL").upper()
        if verdict == "PASS":
            if review.get("adjustment_for_next_turn"):
                coaching_recs["for_seller"] = str(review.get("adjustment_for_next_turn"))
                seller_private["coaching_advice_prev"] = str(review.get("adjustment_for_next_turn"))
            break
        if recommendation:
            buyer_private["coaching_advice_prev"] = recommendation
            coaching_recs["for_buyer"] = recommendation
    text = final_text
    item = {"role": "buyer_ai", "text": text}
    simulation_state["public_transcript"].append({"speaker": "buyer", "text": text})
    simulation_state["next_speaker"] = "seller"
    risk = str(final_review.get("deadlock_risk") or "LOW").upper()
    simulation_state["deadlock_risk"] = risk
    increment_deadlock = risk == "HIGH" or (difficulty == "hard" and risk == "MEDIUM")
    if increment_deadlock:
        session_meta["deadlock_counter"] = int(session_meta.get("deadlock_counter") or 0) + 1
    for p in _extract_agreed_points(text):
        if p not in simulation_state["agreed_points"]:
            simulation_state["agreed_points"].append(p)
    history.append(
        {
            "turn": turn_num,
            "agent": "buyer",
            "draft": final_draft,
            "verdict": str(final_review.get("verdict") or "FAIL"),
            "final_output": text,
            "mentor_note": "",
            "violations": list(final_review.get("violations") or []),
        }
    )
    return item


def simulate_seller_step(analysis: Dict[str, Any], simulation_state: Dict[str, Any]) -> Dict[str, str]:
    """Generate one seller turn (draft->coach->decision->state update)."""
    client = get_model_client()
    seller_private = simulation_state.setdefault("seller_private_context", {})
    coaching_recs = simulation_state.setdefault("coaching_recs", {"for_seller": "", "for_buyer": ""})
    history = simulation_state.setdefault("history", [])
    session_meta = simulation_state.setdefault("session_meta", {})
    difficulty = str(session_meta.get("difficulty") or "medium").lower()
    turn_num = int(session_meta.get("turn_number") or 0) + 1
    session_meta["turn_number"] = turn_num
    session_meta["current_agent"] = "seller"
    if coaching_recs.get("for_seller"):
        seller_private["coaching_advice_prev"] = str(coaching_recs.get("for_seller"))

    final_text = ""
    final_review: Dict[str, Any] = {}
    final_draft = ""
    for _ in range(3):
        text = client.generate_seller_line(analysis, simulation_state)
        final_draft = text
        review = client.evaluate_seller_draft(analysis, simulation_state, text)
        final_review = review
        final_text = text
        recommendation = str(review.get("recommendation") or "").strip()
        verdict = str(review.get("verdict") or "FAIL").upper()
        if verdict == "PASS":
            if review.get("adjustment_for_next_turn"):
                coaching_recs["for_buyer"] = str(review.get("adjustment_for_next_turn"))
                simulation_state.setdefault("buyer_private_context", {})["coaching_advice_prev"] = str(review.get("adjustment_for_next_turn"))
            break
        if recommendation:
            seller_private["coaching_advice_prev"] = recommendation
            coaching_recs["for_seller"] = recommendation

    text = final_text
    item = {"role": "sales_ai", "text": text}
    simulation_state["public_transcript"].append({"speaker": "seller", "text": text})
    simulation_state["next_speaker"] = "buyer"
    risk = str(final_review.get("deadlock_risk") or "LOW").upper()
    simulation_state["deadlock_risk"] = risk
    increment_deadlock = risk == "HIGH" or (difficulty == "hard" and risk == "MEDIUM")
    if increment_deadlock:
        session_meta["deadlock_counter"] = int(session_meta.get("deadlock_counter") or 0) + 1
    for p in _extract_agreed_points(text):
        if p not in simulation_state["agreed_points"]:
            simulation_state["agreed_points"].append(p)
    history.append(
        {
            "turn": turn_num,
            "agent": "seller",
            "draft": final_draft,
            "verdict": str(final_review.get("verdict") or "FAIL"),
            "final_output": text,
            "mentor_note": "",
            "violations": list(final_review.get("violations") or []),
        }
    )
    return item


def simulate_step(
    analysis: Dict[str, Any],
    api_hist: Optional[List[Dict[str, Any]]] = None,
    *,
    simulation_state: Optional[Dict[str, Any]] = None,
    turns: int = 18,
    mentor: bool = True,
    difficulty: str = "medium",
) -> Dict[str, Any]:
    """Run one DEMO turn: reveal the next line from the Demo_AI_negotiation script (legacy api_hist supported)."""
    api_hist = api_hist or []
    state = _coerce_simulation_state(analysis, simulation_state, api_hist)
    diff = str(difficulty or "medium").strip().lower()
    if diff not in {"simple", "medium", "hard"}:
        diff = "medium"
    state.setdefault("session_meta", {})["difficulty"] = diff
    public_transcript = list(state.get("public_transcript") or [])
    turns_total = clamp_demo_turns(int(turns))
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
            "error": None,
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
            "error": None,
        }

    demo_script = list(state.get("demo_script") or [])
    demo_cursor = int(state.get("demo_script_cursor") or 0)

    if len(demo_script) == 0:
        if len(public_transcript) > 0:
            state["public_transcript"] = []
            public_transcript = []
        demo_script = get_model_client().generate_demo_ai_negotiation_script(
            analysis, turn_count=turns_total, difficulty=diff
        )
        state["demo_script"] = demo_script
        state["demo_script_cursor"] = 0
        demo_cursor = 0

    if demo_cursor >= len(demo_script):
        termination = dict(state.get("termination") or {"status": "ongoing", "reason": "", "matched_rule": ""})
        session_meta = state.setdefault("session_meta", {})
        session_meta["status"] = termination.get("status", "ongoing")
        return {
            "ok": True,
            "done": termination.get("status") not in ("", "ongoing"),
            "simulation_state": state,
            "api_hist": transcript_to_legacy_api_hist(list(state.get("public_transcript") or [])),
            "item": None,
            "audit": None,
            "mentor_insight": None,
            "turns_total": turns_total,
            "turns_done": len(state.get("public_transcript") or []),
            "termination": termination,
            "error": None,
        }

    row = demo_script[demo_cursor]
    speaker = str(row.get("speaker") or "").strip().lower()
    if speaker not in ("buyer", "seller"):
        speaker = "buyer" if demo_cursor % 2 == 0 else "seller"
    text = str(row.get("text") or "").strip() or "Let's continue aligning on commercials and next steps."
    role = "buyer_ai" if speaker == "buyer" else "sales_ai"
    item = {"role": role, "text": text}
    state["public_transcript"].append({"speaker": speaker, "text": text})
    state["demo_script_cursor"] = demo_cursor + 1
    state["next_speaker"] = "seller" if speaker == "buyer" else "buyer"

    session_meta = state.setdefault("session_meta", {})
    session_meta["turn_number"] = int(session_meta.get("turn_number") or 0) + 1
    session_meta["current_agent"] = speaker
    session_meta["max_turns"] = turns_total

    history = state.setdefault("history", [])
    history.append(
        {
            "turn": int(session_meta.get("turn_number") or 0),
            "agent": "demo_ai_negotiation",
            "draft": text,
            "verdict": "SCRIPT",
            "final_output": text,
            "mentor_note": "",
            "violations": [],
        }
    )
    for p in _extract_agreed_points(text):
        if p not in state["agreed_points"]:
            state["agreed_points"].append(p)

    public_transcript = list(state.get("public_transcript") or [])
    turns_done = len(public_transcript)
    if turns_done >= turns_total:
        termination = {
            "status": "AGREEMENT",
            "reason": "demo_ai_negotiation script completed",
            "matched_rule": "",
        }
    else:
        termination = {"status": "ongoing", "reason": "", "matched_rule": ""}
    state["termination"] = termination
    session_meta["status"] = termination.get("status", "ongoing")
    done = termination.get("status") != "ongoing"

    audit = None
    if done:
        ui_transcript = [
            {"role": ("buyer_ai" if t.get("speaker") == "buyer" else "sales_ai"), "text": t.get("text", "")}
            for t in public_transcript
        ]
        audit = _audit_transcript(ui_transcript)
        if isinstance(audit, dict):
            forced = _termination_summary(termination)
            if forced:
                audit["summary"] = forced

    mentor_insight: Optional[str] = None
    if mentor:
        mentor_insight = _mentor_insight_for_turn(analysis, item, public_transcript)
        if history:
            history[-1]["mentor_note"] = mentor_insight

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
        "error": None,
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
