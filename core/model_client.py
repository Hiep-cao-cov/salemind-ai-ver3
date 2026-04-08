import json
import os
import re
from functools import lru_cache
from typing import Any, Dict, List, Optional

from utils.logger import get_logger

logger = get_logger(__name__)

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore

try:
    import boto3
except Exception:  # pragma: no cover
    boto3 = None  # type: ignore


class ModelClient:
    def __init__(self) -> None:
        self._openai_client = None
        self._bedrock_client = None

    @property
    def provider(self) -> str:
        preferred = (os.getenv("MODEL_PROVIDER") or "").strip().lower()
        if preferred in {"openai", "bedrock"}:
            return preferred
        if os.getenv("OPENAI_API_KEY"):
            return "openai"
        if os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY"):
            return "bedrock"
        return "fallback"

    def _get_openai(self):
        if self._openai_client is None and OpenAI and os.getenv("OPENAI_API_KEY"):
            self._openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        return self._openai_client

    def _get_bedrock(self):
        if self._bedrock_client is None and boto3 and os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY"):
            region = os.getenv("AWS_DEFAULT_REGION", "ap-southeast-1")
            self._bedrock_client = boto3.client("bedrock-runtime", region_name=region)
        return self._bedrock_client

    def complete(self, prompt: str, *, temperature: float = 0.35, max_tokens: int = 700) -> str:
        provider = self.provider
        logger.info("Calling model provider=%s", provider)
        if provider == "openai":
            client = self._get_openai()
            if client:
                model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                content = response.choices[0].message.content if response.choices else None
                return content or "No response generated."

        if provider == "bedrock":
            client = self._get_bedrock()
            if client:
                model_id = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")
                body = json.dumps(
                    {
                        "anthropic_version": "bedrock-2023-05-31",
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                        "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
                    }
                )
                response = client.invoke_model(modelId=model_id, body=body)
                payload = json.loads(response["body"].read())
                text_blocks = payload.get("content", [])
                text = "\n".join(block.get("text", "") for block in text_blocks if block.get("type") == "text")
                return text or "No response generated."

        return self._fallback_text(prompt)

    def analyze_scenario(self, raw_text: str, mode_key: str, source_name: str = "") -> Dict[str, Any]:
        cleaned = raw_text.strip()
        if not cleaned:
            return {
                "title": source_name or "Untitled Scenario",
                "summary": "No scenario content was provided.",
                "key_points": [],
                "negotiation_points": [],
                "generated_scenario": "",
            }

        provider = self.provider
        if provider in {"openai", "bedrock"}:
            prompt = (
                "Analyze the following negotiation scenario for a B2B chemical commercial training system. "
                "Return strict JSON with keys: title, summary, key_points, negotiation_points. "
                "Each list should have 3 to 6 concise strings.\n\n"
                f"Mode: {mode_key}\n"
                f"Source name: {source_name or 'Direct Input'}\n\n"
                f"Scenario content:\n{cleaned[:12000]}"
            )
            text = self.complete(prompt, temperature=0.2, max_tokens=900)
            parsed = self._extract_json(text)
            if parsed:
                parsed.setdefault("title", source_name or self._derive_title(cleaned))
                parsed.setdefault("summary", self._fallback_summary(cleaned))
                parsed.setdefault("key_points", self._fallback_key_points(cleaned))
                parsed.setdefault("negotiation_points", self._fallback_negotiation_points(cleaned))
                parsed.setdefault("generated_scenario", "")
                return parsed

        return {
            "title": source_name or self._derive_title(cleaned),
            "summary": self._fallback_summary(cleaned),
            "key_points": self._fallback_key_points(cleaned),
            "negotiation_points": self._fallback_negotiation_points(cleaned),
            "generated_scenario": "",
        }

    def create_scenario(self, brief: str, mode_key: str) -> Dict[str, Any]:
        prompt_brief = brief.strip() or "Create a realistic B2B chemical negotiation scenario involving price pressure, payment terms, technical support, and competitor pressure."
        provider = self.provider
        generated = ""
        if provider in {"openai", "bedrock"}:
            prompt = (
                "Create one realistic B2B negotiation scenario for Covestro Strategy Lab. "
                "Keep it detailed but concise, 180 to 260 words, and include business facts that can be negotiated.\n\n"
                f"Mode: {mode_key}\n"
                f"Brief from user: {prompt_brief}"
            )
            generated = self.complete(prompt, temperature=0.5, max_tokens=700)
        if not generated:
            generated = self._fallback_generated_scenario(prompt_brief)
        analysis = self.analyze_scenario(generated, mode_key, "AI Generated Scenario")
        analysis["generated_scenario"] = generated
        return analysis

    def simulate_negotiation(self, analysis: Dict[str, Any], turns: int = 8) -> List[Dict[str, str]]:
        turns = max(8, min(10, turns))
        provider = self.provider
        if provider in {"openai", "bedrock"}:
            prompt = (
                "Create an AI vs AI negotiation transcript as strict JSON list. Each item must have keys role and text. "
                "Alternate between buyer_ai and sales_ai. Use 8 to 10 turns total. The sales side must follow these rules: margin over volume, max payment term 45 days, never reduce price without value exchange.\n\n"
                f"Scenario title: {analysis.get('title', '')}\n"
                f"Scenario summary: {analysis.get('summary', '')}\n"
                f"Key points: {json.dumps(analysis.get('key_points', []))}\n"
                f"Negotiation points: {json.dumps(analysis.get('negotiation_points', []))}\n"
                f"Required turns: {turns}"
            )
            text = self.complete(prompt, temperature=0.55, max_tokens=1400)
            parsed = self._extract_json(text)
            if isinstance(parsed, list):
                normalized: List[Dict[str, str]] = []
                for item in parsed:
                    role = str(item.get("role", "assistant"))
                    text_value = str(item.get("text", "")).strip()
                    if role and text_value:
                        normalized.append({"role": role, "text": text_value})
                if len(normalized) >= 8:
                    return normalized[:10]
        return self._fallback_simulation(analysis, turns)

    def _extract_json(self, text: str) -> Optional[Any]:
        if not text:
            return None
        text = text.strip()
        candidates = [text]
        match = re.search(r"(\{.*\}|\[.*\])", text, re.S)
        if match:
            candidates.insert(0, match.group(1))
        for candidate in candidates:
            try:
                return json.loads(candidate)
            except Exception:
                continue
        return None

    def _derive_title(self, text: str) -> str:
        line = next((ln.strip() for ln in text.splitlines() if ln.strip()), "Negotiation Scenario")
        return line[:90]

    def _fallback_summary(self, text: str) -> str:
        pieces = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
        if not pieces:
            return "Scenario loaded."
        return " ".join(pieces[:2])[:420]

    def _fallback_key_points(self, text: str) -> List[str]:
        rules = [
            ("price", "Strong price pressure is present and the buyer is benchmarking alternatives."),
            ("payment", "Payment terms are a negotiation lever and must stay inside policy."),
            ("support", "Technical support or service scope influences willingness to pay."),
            ("lead", "Lead time or supply continuity matters to the customer decision."),
            ("compet", "Competitor comparison is shaping the customer position."),
            ("volume", "Volume commitment may be used as leverage by the buyer."),
        ]
        lower = text.lower()
        result = [message for key, message in rules if key in lower]
        if not result:
            result = [
                "The customer situation includes commercial pressure and multiple negotiation levers.",
                "The seller must clarify the true decision driver before reacting.",
                "Value defense should stay ahead of any pricing movement.",
            ]
        return result[:5]

    def _fallback_negotiation_points(self, text: str) -> List[str]:
        points = []
        lower = text.lower()
        if "price" in lower:
            points.append("Defend price with total value, not list-price arguments alone.")
        if "payment" in lower or "days" in lower:
            points.append("Do not exceed 45-day payment terms; offer structured alternatives instead.")
        if "technical" in lower or "support" in lower:
            points.append("Use technical support and service differentiation as tradeable value.")
        if "lead" in lower or "supply" in lower:
            points.append("Anchor on supply reliability and lead-time commitment.")
        if "compet" in lower or "basf" in lower or "wanhua" in lower:
            points.append("Reframe competitor comparison to risk, implementation, and support quality.")
        if not points:
            points = [
                "Clarify real needs before conceding anything.",
                "Use value exchange before discussing any commercial movement.",
                "Keep the negotiation disciplined and commercially consistent.",
            ]
        return points[:5]

    def _fallback_generated_scenario(self, brief: str) -> str:
        return (
            f"Customer scenario generated from brief: {brief}. "
            "A regional coatings customer is reviewing annual supply for a specialty material. "
            "The buyer claims the current offer is above competitor benchmarks and asks for price relief plus 60-day payment terms. "
            "At the same time, the customer wants stronger technical support, stable lead time, and supply assurance for a product launch. "
            "The negotiation must balance margin discipline with a credible value story around service, reliability, and risk reduction."
        )

    def _fallback_text(self, prompt: str) -> str:
        lower = prompt.lower()
        if "strict json" in lower and "key_points" in lower:
            analysis = {
                "title": "Negotiation Scenario",
                "summary": "This scenario contains customer pressure on commercials and requires a disciplined value-based response.",
                "key_points": [
                    "The customer is using commercial pressure to move the discussion toward price or terms.",
                    "The seller must clarify the underlying decision drivers before reacting.",
                    "Service, supply reliability, and technical support can be used to defend value.",
                ],
                "negotiation_points": [
                    "Do not move beyond 45-day payment terms.",
                    "No discounting without a corresponding value exchange.",
                    "Reframe toward total business value, not only price.",
                ],
            }
            return json.dumps(analysis)
        return "Thanks for the input. A strong next move is to clarify the real business requirement, defend value first, and avoid policy-breaking concessions."

    def _fallback_simulation(self, analysis: Dict[str, Any], turns: int) -> List[Dict[str, str]]:
        summary = analysis.get("summary", "")
        point = (analysis.get("negotiation_points") or ["Defend value before price."])[0]
        transcript = [
            {"role": "buyer_ai", "text": f"We need a sharper price and longer terms. Based on this case, {summary[:110]}"},
            {"role": "sales_ai", "text": "Before discussing price, let’s align on the real need, implementation risk, and support scope. We need to protect value, not just list price."},
            {"role": "buyer_ai", "text": "BASF is willing to move faster. If you want the volume, we need a more aggressive commercial position."},
            {"role": "sales_ai", "text": "Volume alone does not solve the business case. Our offer includes supply security, technical support, and lower execution risk."},
            {"role": "buyer_ai", "text": "Then at least match 60-day terms so we can justify staying with you."},
            {"role": "sales_ai", "text": "We cannot move beyond 45 days. What we can structure is a phased delivery plan or a service-linked commitment that protects both sides."},
            {"role": "buyer_ai", "text": "If terms stay firm, you need to show a stronger reason to pay more."},
            {"role": "sales_ai", "text": f"That reason is reliability, technical backing, and risk mitigation. {point}"},
        ]
        if turns >= 9:
            transcript.append({"role": "buyer_ai", "text": "If we commit forecast visibility, could you improve the package without touching policy?"})
        if turns >= 10:
            transcript.append({"role": "sales_ai", "text": "Yes, if forecast commitment is real, we can discuss service prioritization or structured implementation support instead of blunt discounting."})
        return transcript[:turns]


@lru_cache(maxsize=1)
def get_model_client() -> ModelClient:
    return ModelClient()
