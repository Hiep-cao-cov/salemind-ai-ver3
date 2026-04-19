from typing import Any, Dict, List

from core.model_client import get_model_client
from modules.module2 import sandbox
from modules.module2.sandbox import _mentor_prior_dialogue, _speaker_label_demo


def prepare_scenario(
    source_type: str,
    source_name: str,
    raw_text: str,
    *,
    use_llm: bool = True,
) -> Dict[str, Any]:
    return get_model_client().analyze_scenario(raw_text, "real_case", source_name, use_llm=use_llm)


def _normalize_role(payload: Dict[str, Any]) -> str:
    role = str(payload.get("practice_role", "") or "").strip().lower()
    return role if role in ("buyer", "seller") else "seller"


def _history_to_public_transcript(history_messages: List[Dict[str, Any]], practice_role: str) -> List[Dict[str, str]]:
    transcript: List[Dict[str, str]] = []
    counterpart = "buyer" if practice_role == "seller" else "seller"
    for msg in history_messages:
        role = str(msg.get("role") or "").strip().lower()
        content = str(msg.get("content") or "").strip()
        if not content:
            continue
        if role == "user":
            transcript.append({"speaker": practice_role, "text": content})
        elif role == "assistant":
            transcript.append({"speaker": counterpart, "text": content})
    return transcript


def _build_real_case_state(analysis: Dict[str, Any], payload: Dict[str, Any], practice_role: str) -> Dict[str, Any]:
    state = sandbox.init_simulation_state(analysis)
    history_messages = payload.get("history_messages")
    if isinstance(history_messages, list):
        transcript = _history_to_public_transcript(history_messages, practice_role)
        state["public_transcript"] = transcript
        state["next_speaker"] = "buyer" if practice_role == "seller" else "seller"
        state["session_meta"]["turn_number"] = len(transcript)
        state["session_meta"]["current_agent"] = state["next_speaker"]
    return state


def _mentor_insight_for_practice_turn(
    analysis: Dict[str, Any],
    item: Dict[str, str],
    public_transcript: List[Dict[str, str]],
    practice_role: str,
) -> str:
    """Practice-only mentor path: ``real_case_mentor_prompt`` + ``mentor_analyze_real_case_turn`` (not DEMO frame)."""
    recent = _mentor_prior_dialogue(public_transcript)
    label = _speaker_label_demo(item.get("role", ""))
    utterance = str(item.get("text") or "")
    return get_model_client().mentor_analyze_real_case_turn(
        practice_role=practice_role,
        speaker_label=label,
        utterance=utterance,
        analysis=analysis,
        recent_dialogue=recent,
    )


def _fallback_mentor_insight(practice_role: str, reply_text: str) -> str:
    side = "buyer" if practice_role == "seller" else "seller"
    trimmed = str(reply_text or "").strip()
    short_reply = trimmed[:220] + ("..." if len(trimmed) > 220 else "")
    return (
        "1) Summary:\n"
        f"The AI {side} has just replied; use it to infer pressure on commercials or relationship.\n\n"
        "2) Tactical analysis:\n"
        "Treat the line as a test of your discipline—avoid conceding before clarifying trade space.\n\n"
        "3) Suggested responses and strategies:\n"
        "- Name one concrete term (price, payment, delivery, volume) to clarify next.\n"
        "- Ask one diagnostic question tied to the latest AI wording.\n"
        f"- Latest AI turn for reference: {short_reply}"
    )


def run(action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    message = payload.get("message", "")
    context_text = payload.get("context_text", "")
    practice_role = _normalize_role(payload)
    analysis = payload.get("analysis")
    if not isinstance(analysis, dict):
        analysis = {}
    difficulty = str(payload.get("difficulty", "medium") or "medium").strip().lower()
    if difficulty not in {"simple", "medium", "hard"}:
        difficulty = "medium"
    mentor_flag = payload.get("mentor", True)
    if isinstance(mentor_flag, str):
        mentor_flag = mentor_flag.strip().lower() in ("1", "true", "yes", "on")
    mentor_enabled = bool(mentor_flag)

    if not context_text.strip():
        reply = "Please upload or paste case material first so the model can summarize it and extract negotiation context."
        return {"reply": reply, "audit": {}}

    if action in {"help", "coach"}:
        reply = (
            "Real Case coaching: use the same DEMO discipline. "
            "Clarify needs, defend value, and trade concessions only with clear reciprocity."
        )
        return {"reply": reply, "audit": {}}

    state = _build_real_case_state(analysis, payload, practice_role)
    state.setdefault("session_meta", {})["difficulty"] = difficulty
    if practice_role == "seller":
        item = sandbox.simulate_buyer_step(analysis, state)
    else:
        item = sandbox.simulate_seller_step(analysis, state)
    reply = str(item.get("text") or "")
    mentor_insight = ""
    if mentor_enabled:
        try:
            mentor_insight = str(
                _mentor_insight_for_practice_turn(
                    analysis,
                    item,
                    list(state.get("public_transcript") or []),
                    practice_role,
                )
                or ""
            ).strip()
        except Exception:
            mentor_insight = ""
        if not mentor_insight:
            mentor_insight = _fallback_mentor_insight(practice_role, reply)
    result: Dict[str, Any] = {"reply": reply, "audit": {}}
    if mentor_enabled:
        result["mentor_insight"] = mentor_insight
    return result
