"""
Mentor analysis for each AI-vs-AI line in Sandbox DEMO (step-by-step).

Rules text: ``data/prompts/demo_mentor_rule.txt``. Tunables: ``data/config.txt`` ([demo_mentor]). Independent of Practice mentor.
"""

import re

from utils.ai_output_config import get_int


def get_demo_mentor_max_words() -> int:
    return get_int("demo_mentor", "max_words", 60)


def get_demo_mentor_scenario_chars() -> int:
    return get_int("demo_mentor", "scenario_context_chars", 4000)


# Back-compat constant (static); runtime limits use getters above.
MENTOR_MAX_WORDS = 60


_MAX_SCENARIO_CHARS = 4000  # legacy name; use get_demo_mentor_scenario_chars() in builders


def normalize_mentor_text(raw: str, *, max_words: int | None = None) -> str:
    """
    Strip noise, collapse whitespace, cap at max_words (default from config).
    """
    limit = get_demo_mentor_max_words() if max_words is None else max_words
    if not raw or not str(raw).strip():
        return ""
    text = str(raw).strip()
    text = re.sub(r"```[\s\S]*?```", " ", text)
    text = re.sub(r"^#{1,6}\s+.+$", " ", text, flags=re.MULTILINE)
    text = re.sub(r"\s+", " ", text).strip()
    words = text.split()
    if not words:
        return ""
    if len(words) > limit:
        words = words[:limit]
        text = " ".join(words).rstrip(",;:")
        if text and text[-1].isalnum():
            text += "…"
    else:
        text = " ".join(words)
    return text


def build_demo_turn_mentor_prompt(
    *,
    speaker_label: str,
    utterance: str,
    scenario_context: str,
    recent_dialogue: str,
    mentor_rules: str = "",
    max_words: int | None = None,
) -> str:
    """
    max_words defaults from config; pass explicitly to override.
    """
    n = get_demo_mentor_max_words() if max_words is None else max_words
    cap = get_demo_mentor_scenario_chars()
    content = (utterance or "").strip()
    if not content:
        content = "(No text in this turn.)"

    scenario = (scenario_context or "").strip()[:cap]
    if not scenario:
        scenario = "(No scenario summary.)"
    recent = (recent_dialogue or "").strip() or "(No prior lines in this thread.)"

    rules_text = (mentor_rules or "").strip() or (
        "Analyze the latest turn and provide concise educational guidance with hidden intent, technique, watchout, and short advice."
    )

    return f"""You are a master negotiator coaching B2B sales learners (e.g. Covestro-style chemicals deals).

TASK: Write ONE short paragraph that helps the learner understand THIS turn only.

QUOTED TURN ({speaker_label}):
\"\"\"{content}\"\"\"

Scenario (facts — do not contradict):
{scenario}

Prior dialogue (context):
{recent}

Mentor rules:
{rules_text}

In your paragraph, in plain English:
- What this counterpart line really signals (substance + pressure).
- Likely tactic (price, payment, time, competition, risk, relationship).
- One concrete suggestion for the seller (value defense, questions to ask, or concession to avoid).

RULES:
- Maximum {n} words. No bullet lists, no markdown headings, no numbering.
- Stay tied to the quoted line; avoid generic advice that ignores what was actually said.
- Output only the paragraph, nothing else."""


def fallback_demo_mentor_note(speaker_label: str, utterance: str) -> str:
    u = (utterance or "").strip()
    if not u:
        return normalize_mentor_text(
            "No line to analyze in this turn. Run the next simulation step when the AI has spoken."
        )
    clip = u[:120] + ("…" if len(u) > 120 else "")
    raw = (
        f"In this turn, {speaker_label} is pushing themes visible in: “{clip}”. "
        f"Read it as commercial pressure tied to that wording—often price, terms, speed, or risk transfer. "
        f"As seller, clarify the underlying need, anchor on service and supply value, and avoid conceding before trading something back."
    )
    return normalize_mentor_text(raw)
