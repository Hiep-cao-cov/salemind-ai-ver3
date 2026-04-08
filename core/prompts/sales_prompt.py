from core.prompts.system_prompt import MODE_GUIDANCE, SYSTEM_FOUNDATION


def build_sales_prompt(mode: str, user_message: str, context_text: str = "") -> str:
    parts = [SYSTEM_FOUNDATION, f"Mode guidance: {MODE_GUIDANCE.get(mode, '')}", "Sales method: clarify -> anchor -> defend -> reframe."]
    if context_text:
        parts.append(f"Scenario context:\n{context_text[:8000]}")
    parts.append(f"Buyer or user input:\n{user_message}")
    parts.append("Respond as a disciplined B2B chemical commercial sales professional.")
    return "\n\n".join(parts)
