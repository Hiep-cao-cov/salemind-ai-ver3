"""
Central AI output / sampling parameters from ``data/config.txt``.

Use :func:`clear_ai_output_config_cache` in tests if you need a fresh read.
"""

from __future__ import annotations

from configparser import ConfigParser
from functools import lru_cache
from pathlib import Path

_CONFIG_PATH = Path("data/config.txt")


@lru_cache(maxsize=1)
def _parser() -> ConfigParser:
    p = ConfigParser()
    if _CONFIG_PATH.exists():
        p.read(_CONFIG_PATH, encoding="utf-8")
    return p


def clear_ai_output_config_cache() -> None:
    _parser.cache_clear()


def get_int(section: str, key: str, default: int) -> int:
    cp = _parser()
    if not cp.has_section(section) or not cp.has_option(section, key):
        return default
    try:
        return int(cp.get(section, key).strip().split()[0])
    except (TypeError, ValueError):
        return default


def get_float(section: str, key: str, default: float) -> float:
    cp = _parser()
    if not cp.has_section(section) or not cp.has_option(section, key):
        return default
    try:
        return float(cp.get(section, key).strip().split()[0])
    except (TypeError, ValueError):
        return default


def clamp_demo_turns(n: int) -> int:
    lo = get_int("demo_simulate", "turns_min", 16)
    hi = get_int("demo_simulate", "turns_max", 20)
    return max(lo, min(hi, int(n)))


def demo_turns_default() -> int:
    return clamp_demo_turns(get_int("demo_simulate", "turns_default", 18))


def apply_demo_script_hard_word_cap(speaker: str, text: str) -> str:
    """
    Optional post-process for Demo_AI_negotiation lines ([demo_ai_negotiation] *_hard_max_words).
    """
    sp = str(speaker or "").strip().lower()
    if sp not in ("buyer", "seller"):
        return text
    key = "buyer_hard_max_words" if sp == "buyer" else "seller_hard_max_words"
    cap = get_int("demo_ai_negotiation", key, 0)
    if cap <= 0:
        return (text or "").strip()
    t = (text or "").strip()
    words = t.split()
    if len(words) <= cap:
        return t
    clipped = " ".join(words[:cap]).rstrip(",;:")
    if clipped and clipped[-1].isalnum():
        return clipped + "…"
    return clipped + "…"
