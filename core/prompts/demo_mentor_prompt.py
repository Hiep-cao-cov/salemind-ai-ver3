"""
Mentor analysis for each AI-vs-AI line in Sandbox DEMO (step-by-step).

Tune the summary length here (one place):
"""

import re

# ---------------------------------------------------------------------------
# USER-TUNABLE: target length for mentor text (hard stop after this many words)
# ---------------------------------------------------------------------------
MENTOR_MAX_WORDS = 60

_MAX_SCENARIO_CHARS = 4000


def normalize_mentor_text(raw: str, *, max_words: int | None = None) -> str:
    """
    Strip noise, collapse whitespace, cap at max_words (default: MENTOR_MAX_WORDS).
    """
    limit = MENTOR_MAX_WORDS if max_words is None else max_words
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
    max_words: int | None = None,
) -> str:
    """
    max_words defaults to MENTOR_MAX_WORDS; pass explicitly to keep prompt in sync.
    """
    n = MENTOR_MAX_WORDS if max_words is None else max_words
    content = (utterance or "").strip()
    if not content:
        content = "(No text in this turn.)"

    scenario = (scenario_context or "").strip()[:_MAX_SCENARIO_CHARS]
    if not scenario:
        scenario = "(No scenario summary.)"
    recent = (recent_dialogue or "").strip() or "(No prior lines in this thread.)"

    return f"""You are a master negotiator coaching B2B sales learners (e.g. Covestro-style chemicals deals).

TASK: Write ONE short paragraph that helps the learner understand THIS turn only.

QUOTED TURN ({speaker_label}):
\"\"\"{content}\"\"\"

Scenario (facts — do not contradict):
{scenario}

Prior dialogue (context):
{recent}

In your paragraph, in plain English:
- What this line means in plain language (the “real message”).
- What tactic or pressure it uses (price, payment, time, competition, risk, relationship, etc.).
- One practical angle for the seller (value defense, questions to ask, or what not to give away first).

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
