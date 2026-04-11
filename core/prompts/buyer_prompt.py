from core.prompts.system_prompt import MODE_GUIDANCE, SYSTEM_FOUNDATION


def build_buyer_prompt(
    mode: str,
    sales_message: str,
    persona: str = "price-driven",
    context_text: str = "",
) -> str:
    parts = [
        SYSTEM_FOUNDATION,
        "",
        f"Mode guidance: {MODE_GUIDANCE.get(mode, '')}",
    ]
    if context_text.strip():
        parts.extend(["", "Scenario / case context (stay consistent with this):", context_text[:6000]])
    parts.extend(
        [
            "",
            f"Buyer persona: {persona}. Use realistic pressure tactics such as anchoring low, deadline pressure, competition leverage, and skepticism.",
            "",
            "Sales message to challenge:",
            sales_message,
            "",
            "Reply as the buyer in a natural negotiation tone.",
        ]
    )
    return "\n".join(parts)
