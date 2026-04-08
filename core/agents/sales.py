from core.model_client import get_model_client
from core.prompts.sales_prompt import build_sales_prompt

PAYMENT_LIMIT_DAYS = 45


def sales_response(mode: str, user_message: str, context_text: str = "") -> str:
    forced = _guardrail_override(user_message)
    if forced:
        return forced
    prompt = build_sales_prompt(mode, user_message, context_text)
    return get_model_client().complete(prompt)


def sales_help(mode: str, user_message: str, context_text: str = "") -> str:
    return (
        "Tactical hint: clarify the real need first, then defend value before discussing price. "
        f"Payment terms must remain within {PAYMENT_LIMIT_DAYS} days. Trade service, supply reliability, or commitment structure before touching price."
    )


def sales_auto(mode: str, user_message: str, context_text: str = "") -> str:
    forced = _guardrail_override(user_message)
    if forced:
        return forced
    return (
        "Before discussing any price movement, let’s align on the real business requirement, supply continuity, technical support scope, and implementation risk. "
        f"If we improve terms at all, it must come with a clear value exchange, and payment terms need to remain within our {PAYMENT_LIMIT_DAYS}-day policy."
    )


def _guardrail_override(user_message: str) -> str:
    lower = user_message.lower()
    if "60 days" in lower or "90 days" in lower or "payment term 60" in lower:
        return (
            "We cannot move beyond a 45-day payment term. What we can explore instead is a structured delivery plan, service prioritization, "
            "or a volume-linked commitment that protects both sides without breaking policy."
        )
    return ""
