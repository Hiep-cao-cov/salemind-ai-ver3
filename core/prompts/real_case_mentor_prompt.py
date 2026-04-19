"""
Mentor commentary for Practice (real_case) mode only.

Uses ``real_case_mentor_rule.txt`` and ``[real_case_mentor]`` in config—no coupling to DEMO mentor assets.
"""

import re

from utils.ai_output_config import get_int


def get_real_case_mentor_max_words() -> int:
    return get_int("real_case_mentor", "max_words_total", 200)


def get_real_case_mentor_scenario_chars() -> int:
    return get_int("real_case_mentor", "scenario_context_chars", 4000)


# Back-compat (static); runtime uses getters.
REAL_CASE_MENTOR_MAX_WORDS = 200


def normalize_real_case_mentor_text(raw: str, *, max_words: int | None = None) -> str:
    """
    Clean model output while keeping paragraph breaks (section 1 / 2 / 3).
    Hard-cap total words across the whole message.
    """
    limit = get_real_case_mentor_max_words() if max_words is None else max_words
    text = (raw or "").strip()
    if not text:
        return ""
    text = re.sub(r"```[\s\S]*?```", " ", text)
    text = re.sub(r"(?m)^[#]{1,6}\s+.+$", " ", text)
    blocks = re.split(r"\n\s*\n+", text)
    cleaned: list[str] = []
    for block in blocks:
        inner = " ".join(block.split())
        if inner.strip():
            cleaned.append(inner.strip())
    text = "\n\n".join(cleaned)
    words = text.split()
    if not words:
        return ""
    if len(words) > limit:
        words = words[:limit]
        text = " ".join(words).rstrip(",;:")
        if text and text[-1].isalnum():
            text += "…"
        return text
    return text


def build_real_case_mentor_prompt(
    *,
    practice_role: str,
    speaker_label: str,
    utterance: str,
    scenario_context: str,
    recent_dialogue: str,
    mentor_rules: str = "",
    max_words: int | None = None,
) -> str:
    """
    Frame for Mentor after the AI counterpart speaks in Practice mode.
    The learner plays ``practice_role`` (seller or buyer); the quoted turn is the AI line.
    """
    _ = max_words  # optional override reserved for callers; cap from config in prompt
    learner_side = "Covestro sales (seller)" if practice_role == "seller" else "customer (buyer)"
    counterpart_side = "AI buyer" if practice_role == "seller" else "AI seller"

    content = (utterance or "").strip()
    if not content:
        content = "(No text in this turn.)"

    scenario = (scenario_context or "").strip()[: get_real_case_mentor_scenario_chars()]
    if not scenario:
        scenario = "(No scenario summary.)"
    recent = (recent_dialogue or "").strip() or "(No prior lines in this thread.)"

    rules_text = (mentor_rules or "").strip() or (
        "Give concise coaching: hidden intent, technique, one watchout, one actionable tip for the learner."
    )

    return f"""You are a negotiation coach for B2B Practice mode (Covestro Strategy Lab).

CONTEXT: The human learner is playing **{learner_side}**. The line below was spoken by the **{counterpart_side}** ({speaker_label}) in response to the ongoing thread.

QUOTED COUNTERPART TURN ({speaker_label}):
\"\"\"{content}\"\"\"

Scenario / case facts (do not contradict):
{scenario}

Prior dialogue (thread context):
{recent}

Mentor rules (substance; do not contradict the OUTPUT FORMAT below):
{rules_text}

TASK — OUTPUT FORMAT (Practice / real_case ONLY):
Write **the entire output in English only**. Write **exactly three sections** for the human learner. Start each section with **these exact English titles** on the first line (keep them verbatim), then your coaching text on the same line or following lines until the next section title.

1) Summary:
   - Paraphrase what the counterpart’s line really means for the negotiation (substance + pressure).
   - Target **about 30–40 words** in this section (English).

2) Tactical analysis:
   - Name the tactic(s) (e.g. price anchor, payment stretch, time pressure, competition reference, risk transfer, relationship leverage, Scope 3 / ESG squeeze, nibble, good cop / bad cop).
   - Target **about 20–30 words** in this section (English).

3) Suggested responses and strategies:
   - Give **3–5 concrete options** the learner ({learner_side}) can use next: questions to ask, value anchors, reciprocal trades, or moves to avoid.
   - You **may** use a short bullet list with leading "- " **only inside this section** (English).
   - Stay grounded in the quoted line and scenario; avoid generic platitudes.

GLOBAL RULES:
- Coach the **human learner** only — do not write as if coaching the AI character.
- Separate the three sections with **one blank line** between sections.
- Do not use markdown headings (#). Do not repeat the entire quoted turn verbatim.
- Total output should stay within roughly **{get_real_case_mentor_max_words()} words** across all sections (including titles)."""


def fallback_real_case_mentor_note(practice_role: str, speaker_label: str, utterance: str) -> str:
    """Offline fallback when no LLM provider is configured."""
    u = (utterance or "").strip()
    learner = "seller" if practice_role == "seller" else "buyer"
    if not u:
        return normalize_real_case_mentor_text(
            "1) Summary:\nNo counterpart line to analyze yet. Continue the negotiation once the AI has spoken.\n\n"
            "2) Tactical analysis:\n—\n\n"
            "3) Suggested responses and strategies:\n"
            "- Clarify one priority commercial lever (price, payment, delivery, or volume).\n"
            "- Ask one sharp question to surface the real need before conceding.\n"
            "- Re-anchor on full-package value instead of headline price alone."
        )
    clip = u[:120] + ("…" if len(u) > 120 else "")
    raw = (
        f"1) Summary:\n{speaker_label} is applying commercial pressure through: “{clip}” — read for "
        f"underlying drivers (money, risk, time, ESG), not only surface wording.\n\n"
        f"2) Tactical analysis:\nLikely a probe of your reaction while keeping initiative; avoid "
        f"being pulled into one-sided concessions.\n\n"
        f"3) Suggested responses and strategies:\n"
        f"- Clarify decision criteria and insist on a like-for-like comparison.\n"
        f"- Use an if–then frame to trade any movement for reciprocal commitment.\n"
        f"- If you are the Covestro seller, anchor service, supply, or sustainability value; if you are the buyer, test the counterpart’s claims with specifics."
    )
    return normalize_real_case_mentor_text(raw)
