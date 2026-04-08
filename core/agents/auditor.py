from typing import Dict


VALUE_TERMS = ["supply", "support", "lead time", "risk", "service", "technical", "incoterms", "reliability"]


def audit_response(text: str) -> Dict[str, object]:
    lower = text.lower()
    flags = {
        "discount_violation": any(term in lower for term in ["discount", "rebate"]) and "value" not in lower,
        "payment_term_violation": any(term in lower for term in ["60 days", "90 days", "75 days"]),
        "weak_positioning": "okay" in lower and not any(term in lower for term in VALUE_TERMS),
        "missed_value_defense": "price" in lower and not any(term in lower for term in VALUE_TERMS),
    }
    suggestions = []
    if flags["discount_violation"]:
        suggestions.append("Avoid discounting without a clear value exchange.")
    if flags["payment_term_violation"]:
        suggestions.append("Keep payment terms within the 45-day policy limit.")
    if flags["weak_positioning"]:
        suggestions.append("Anchor more firmly on business value and commercial discipline.")
    if flags["missed_value_defense"]:
        suggestions.append("Use supply security, technical support, and risk mitigation to defend value.")
    return {
        "flags": flags,
        "summary": " ".join(suggestions) if suggestions else "Commercial discipline is intact.",
    }
