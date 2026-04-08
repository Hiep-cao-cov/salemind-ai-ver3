from core.prompts.system_prompt import MODE_GUIDANCE, SYSTEM_FOUNDATION


def build_buyer_prompt(mode: str, sales_message: str, persona: str = "price-driven") -> str:
    return (
        f"{SYSTEM_FOUNDATION}\n\n"
        f"Mode guidance: {MODE_GUIDANCE.get(mode, '')}\n"
        f"Buyer persona: {persona}. Use realistic pressure tactics such as anchoring low, deadline pressure, competition leverage, and skepticism.\n\n"
        f"Sales message to challenge:\n{sales_message}\n\n"
        "Reply as the buyer in a natural negotiation tone."
    )
