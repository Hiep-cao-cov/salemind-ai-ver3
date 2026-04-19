"""User-message audit for Practice (real_case): scenario fit + company policy.

Policy rules MUST come only from ``data/Startegy_policy.txt`` (no other policy source).
Scenario alignment uses the provided scenario context string only.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict

from core.model_client import get_model_client
from core.prompt_loader import get_strategy_policy_text
from utils.logger import get_logger

logger = get_logger(__name__)


def load_strategy_policy_text() -> str:
    """Return verbatim company strategy/policy from ``data/Startegy_policy.txt`` only."""
    return get_strategy_policy_text()


def _extract_json_object(text: str) -> Dict[str, Any] | None:
    text = (text or "").strip()
    if "{" not in text or "}" not in text:
        return None
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        return json.loads(text[start:end])
    except (ValueError, json.JSONDecodeError):
        return None


def _fallback_audit(user_message: str, scenario_context: str, policy: str) -> Dict[str, Any]:
    """Lightweight offline check: policy line hints + minimal scenario overlap."""
    u = (user_message or "").lower()
    notes: list[str] = []

    if "60 day" in u or "90 day" in u or "75 day" in u:
        notes.append("Payment terms may conflict with the 45-day policy stated in Startegy_policy.txt.")
    if "discount" in u or "rebate" in u:
        if "value" not in u and "service" not in u and "volume" not in u:
            notes.append("Discount/rebate language without a clear value trade may breach commercial discipline in Startegy_policy.txt.")
    if policy and scenario_context:
        sc = scenario_context.lower()[:4000]
        overlap = sum(1 for w in re.findall(r"[a-zA-Z]{5,}", u) if len(w) > 5 and w in sc)
        if overlap < 2 and len(u.split()) > 6:
            notes.append("Limited linkage to scenario facts—tie claims to the case brief.")

    if not notes:
        notes.append(
            "Heuristic pass only (no model): no obvious keyword conflicts with Startegy_policy.txt; "
            "self-check against the policy file."
        )
    return {"summary": " ".join(notes)[:420], "flags": {"heuristic": True}}


def audit_real_case_user_message(user_message: str, scenario_context: str) -> Dict[str, Any]:
    """
    Evaluate the learner USER turn for (1) scenario fit and (2) violations of rules that appear
    ONLY in ``data/Startegy_policy.txt``.
    """
    policy = load_strategy_policy_text().strip()
    user_message = (user_message or "").strip()
    scenario_context = (scenario_context or "").strip()

    if not user_message:
        return {"summary": "", "flags": {}}

    if not policy:
        return {
            "summary": "Company policy file data/Startegy_policy.txt is missing or empty; audit skipped.",
            "flags": {"policy_missing": True},
        }

    prompt = (
        "Return ONLY a JSON object with keys \"summary\" (string, max 380 characters, English) "
        'and \"flags\" (object; optional short keys).\n\n'
        "You audit a LEARNER (user) message in a B2B negotiation role-play.\n\n"
        "=== COMPANY STRATEGY AND POLICY (sole authority for policy/strategy rules; do not invent other company rules) ===\n"
        f"{policy[:14000]}\n"
        "=== END POLICY ===\n\n"
        "=== NEGOTIATION SCENARIO CONTEXT (for situational fit / factual consistency only) ===\n"
        f"{scenario_context[:8000]}\n"
        "=== END SCENARIO ===\n\n"
        "=== USER MESSAGE ===\n"
        f"{user_message[:8000]}\n"
        "=== END USER MESSAGE ===\n\n"
        "Tasks:\n"
        "1) Briefly assess whether the user message fits the scenario context.\n"
        "2) Note any clear violations of the POLICY section above (cite behavior, not clause numbers).\n"
        "If aligned and no violation: one concise positive sentence in summary.\n"
        "Output JSON only, no markdown fences."
    )

    try:
        raw = get_model_client().complete(prompt, temperature=0.15, max_tokens=400)
        parsed = _extract_json_object(raw)
        if isinstance(parsed, dict):
            summary = str(parsed.get("summary") or "").strip()
            if summary:
                flags = parsed.get("flags")
                return {
                    "summary": summary[:400],
                    "flags": flags if isinstance(flags, dict) else {},
                }
    except Exception as exc:  # pragma: no cover
        logger.info("real_case user audit model path failed: %s", exc)

    return _fallback_audit(user_message, scenario_context, policy)
