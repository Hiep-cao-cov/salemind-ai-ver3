"""
Demo_AI_negotiation — single-writer DEMO transcript (Sandbox).

Replaces per-turn Buyer/Seller agent calls with one scripted conversation
authored by one LLM role, then replayed turn-by-turn in ``simulate_step``.

Per-turn length targets are controlled from ``data/config.txt`` ([demo_ai_negotiation]).
"""

from __future__ import annotations

from utils.ai_output_config import apply_demo_script_hard_word_cap, clamp_demo_turns, get_int


def _skill_excerpt_max() -> int:
    return get_int("demo_ai_negotiation", "skill_excerpt_chars", 3200)


def _length_rules_for_role(role: str, human_label: str) -> str:
    smin = get_int("demo_ai_negotiation", f"{role}_turn_text_min_sentences", 1)
    smax = get_int("demo_ai_negotiation", f"{role}_turn_text_max_sentences", 4)
    wmin = get_int("demo_ai_negotiation", f"{role}_turn_text_min_words", 0)
    wmax = get_int("demo_ai_negotiation", f"{role}_turn_text_max_words", 0)
    hard = get_int("demo_ai_negotiation", f"{role}_hard_max_words", 0)
    parts = [
        f"{human_label} (`speaker` = `{role}`): **{smin}–{smax} sentences** per `text`; "
        f'natural spoken dialogue only (no "{role}:" prefix inside the string).'
    ]
    if wmin > 0 and wmax > 0 and wmax >= wmin:
        parts.append(f"Aim **{wmin}–{wmax} English words** in that same turn when compatible with the sentence band.")
    if hard > 0:
        parts.append(f"Never exceed **{hard} words** in that `text` (hard ceiling).")
    return " ".join(parts)


def _turn_length_instruction() -> str:
    b = _length_rules_for_role("buyer", "Buyer")
    s = _length_rules_for_role("seller", "Covestro seller")
    return (
        "LENGTH BY ROLE — apply the matching band to **every** `turns[]` item using its `speaker` value:\n"
        f"- {b}\n"
        f"- {s}"
    )


def _difficulty_contract(diff: str) -> str:
    """
    Strong, visibly different arcs for SIMPLE vs MEDIUM vs HARD so trainers
    immediately notice a difficulty change when re-running DEMO on the same scenario.
    """
    d = (diff or "medium").strip().lower()
    if d not in {"simple", "medium", "hard"}:
        d = "medium"

    simple = """**DIFFICULTY = SIMPLE (must read as clearly easier than Medium/Hard):**
- **Buyer**: constructive procurement—clear asks but **low interpersonal heat**; prefers package language (“what would a balanced package look like?”); **at most one** competitive/alternative-supplier threat in the **whole** transcript, and keep it professional, not punitive.
- **Seller**: confidently explains value and **offers structured trades earlier** (still no policy-breaking terms); willing to **confirm alignment** on several pillars (price band, payment, volume/tenure) **before the last ~25% of turns** so the thread feels **cooperative problem-solving**.
- **Arc**: **two** main tension beats (e.g. price anchor → package resolution); by turn **~ceil(0.65×N)** the parties should be **largely aligned** on the commercial frame; final turns = **clean documentation / next-step** tone, not a last-minute ambush.
- **Explicit contrast**: avoid long chains of buyer “take it or leave it” lines; avoid seller stonewalling past the midpoint."""

    medium = """**DIFFICULTY = MEDIUM (default balanced B2B):**
- **Buyer**: **credible pressure**—anchors, tests, and **occasional** competition or board timeline; demands **reciprocity** before moving; may **re-open one issue once** after seeming progress (classic procurement).
- **Seller**: **disciplined Covestro**—defends margin, **if–then** framing, no headline discount without traded value; concedes in **small, earned steps** after buyer clarifies scope.
- **Arc**: **three** tension beats (open → squeeze → package/trade → near-close); major movement on commercials should not appear until **past the midpoint** of the transcript; close still requires a **clear recap** of what is traded for what.
- **Explicit contrast**: noticeably **more friction and fewer early giveaways** than SIMPLE; noticeably **less brutality and fewer multi-issue pile-ons per buyer turn** than HARD."""

    hard = """**DIFFICULTY = HARD (must read as clearly tougher than Medium—trainee should feel heat):**
- **Buyer**: **strategic, high-pressure procurement**—often **bundles 2–3 levers in one turn** (e.g. price + payment + ESG/Scope 3 or volume + tenure); uses **credible time pressure** and **at least two** distinct references to **alternatives, benchmarks, or internal gatekeepers** across the transcript; may **withdraw a prior “signal”** or tighten terms if seller moves too slowly.
- **Seller**: **minimal early movement**; **more “prove it / document it”** responses; major commercial movement only **after** buyer has traded something measurable (forecast, tenure, scope); **no free concessions**—every improvement is **explicitly packaged**.
- **Arc**: **at least four** distinct waves of buyer pressure after the opening; **no comfortable settlement** before **past 60% of turns**; include **one late-stage sharp test** (e.g. final nibbling on payment, carbon claims, or liability) **before** a deal or a **firm walk-away / pause with reasons**.
- **Explicit contrast**: transcript must **not** feel like SIMPLE (no early warm alignment); buyer language can be **blunter** but stay professional (no abuse, no slurs)."""

    return {"simple": simple, "medium": medium, "hard": hard}[d]


def _clip(text: str, limit: int) -> str:
    t = (text or "").strip()
    if len(t) <= limit:
        return t
    return t[:limit].rstrip() + "…"


def build_demo_ai_negotiation_prompt(
    *,
    scenario_context: str,
    strategy_policy: str,
    seller_skill_excerpt: str,
    buyer_skill_excerpt: str,
    turn_count: int,
    difficulty: str,
) -> str:
    n = clamp_demo_turns(int(turn_count))
    diff = (difficulty or "medium").strip().lower()
    if diff not in {"simple", "medium", "hard"}:
        diff = "medium"

    policy = (strategy_policy or "").strip() or "(No separate policy file text; use Covestro value-selling discipline.)"
    ctx = (scenario_context or "").strip() or "(No scenario context.)"
    skill_cap = _skill_excerpt_max()
    turn_rule = _turn_length_instruction()
    diff_contract = _difficulty_contract(diff)

    return f"""You are **Demo_AI_negotiation**, a single authoring agent for a training simulation.

Your job is to write **one complete, realistic B2B negotiation transcript** between:
- **Seller**: Covestro commercial representative (polyurethanes, polycarbonates, or specialty materials as the scenario implies).
- **Buyer**: Customer-side procurement / technical buying (professional, not cartoonish).

**Expert bar (negotiation craft):** Write every `text` as a **senior practitioner** would on a live call—commercially literate, calm under pressure, and specific on levers (price, payment, freight, volume, risk, tenure, ESG / Scope 3 where relevant). Show **credible moves**: anchors, tests, reciprocity (“if–then”), trade packages, and closing signals—not textbook lists inside the dialogue, not melodrama, not generic filler. Buyer should sound like experienced strategic procurement; seller like **disciplined principal-level** Covestro sales defending value without sounding robotic.

You must output **valid JSON only** (no markdown fences, no commentary before or after the JSON). Schema:
{{
  "turns": [
    {{"speaker": "buyer", "text": "<spoken dialogue>"}},
    {{"speaker": "seller", "text": "<spoken dialogue>"}}
  ]
}}

STRICT RULES:
1. Exactly **{n}** objects in `"turns"`, alternating speakers starting with **buyer** (turn 1 = buyer opening).
2. First buyer line: brief, natural opening (light time acknowledgement at most if it fits), then substantive commercial pressure **grounded in the scenario** — avoid stacked “thank you so much / I appreciate” filler.
3. Progress the thread from opening through tension to a **clear close** (deal agreed **or** explicit walk-away / pause) in the final turns — no abrupt truncation.
4. Obey **Covestro strategy** in seller lines: full-package economics, margin discipline, reciprocity (“if–then”), no price in isolation, sustainability as traded value where relevant — aligned with the skill excerpts below.
5. Obey **company strategy / policy** text below verbatim where it applies; do not contradict it.
6. Stay faithful to **scenario facts**; do not invent confidential Covestro numbers unless the scenario already states them.
7. **Difficulty is `{diff}` (uppercase label for the model: {diff.upper()})** — obey the contract below **literally** so a trainer comparing runs on the **same scenario** immediately sees a different **pace, buyer harshness, and seller rigidity**.
8. Each line should **move the deal forward** (clarify, pressure, trade, or commit)—avoid throat-clearing, vague politeness chains, or meta commentary (“as negotiators we should…”).
9. {turn_rule}

{diff_contract}

Scenario and analysis context:
{ctx}

Company strategy / policy (verbatim guidance for the simulation):
{policy}

Seller-side discipline excerpt (Covestro representative — follow spirit):
{_clip(seller_skill_excerpt, skill_cap)}

Buyer-side discipline excerpt (customer pressure — follow spirit):
{_clip(buyer_skill_excerpt, skill_cap)}

Return the JSON object now."""


def fallback_demo_script_turns(turn_count: int) -> list[dict[str, str]]:
    """Deterministic alternating lines when no LLM provider is configured."""
    n = clamp_demo_turns(int(turn_count))
    buyer = (
        "Thanks for joining today—we need to reset commercials on this grade; "
        "our board is comparing you to a lower headline from another supplier."
    )
    seller = (
        "Understood. Before we touch price, let’s align on like-for-like scope—Incoterms, service, "
        "and what you need on supply continuity—then we can discuss a structured package."
    )
    out: list[dict[str, str]] = []
    for i in range(n):
        sp = "buyer" if i % 2 == 0 else "seller"
        if i == 0:
            text = buyer
        elif i == 1:
            text = seller
        elif i == n - 1:
            text = (
                "We’re aligned on the package you outlined—let’s document price, payment, and volume "
                "as discussed and move to contract language."
                if sp == "buyer"
                else "Agreed—I'll confirm those terms in writing today and share the draft schedule."
            )
        else:
            text = (
                "We still need movement on the payment window if you want the volume commitment we discussed."
                if sp == "buyer"
                else "We can consider 45 days net if we lock the forecast band and extend the agreement term as proposed."
            )
        out.append({"speaker": sp, "text": apply_demo_script_hard_word_cap(sp, text)})
    return out
