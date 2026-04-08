from core.model_client import get_model_client
from core.prompts.buyer_prompt import build_buyer_prompt


def buyer_response(mode: str, sales_message: str, persona: str = "price-driven") -> str:
    prompt = build_buyer_prompt(mode, sales_message, persona)
    return get_model_client().complete(prompt)
