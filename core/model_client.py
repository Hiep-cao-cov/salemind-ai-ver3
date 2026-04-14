import json
import os
import re
from functools import lru_cache
from typing import Any, Dict, List, Optional

from utils.logger import get_logger

from core.prompts.demo_mentor_prompt import (
    MENTOR_MAX_WORDS,
    build_demo_turn_mentor_prompt,
    fallback_demo_mentor_note,
    normalize_mentor_text,
)
from core.prompts.system_prompt import SYSTEM_FOUNDATION

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

    def complete_chat(
        self,
        messages: List[Dict[str, str]],
        *,
        temperature: float = 0.4,
        max_tokens: int = 520,
    ) -> str:
        """
        Multi-turn chat API (option C): roles user/assistant alternate; system first.
        """
        if not messages:
            return "No response generated."

        provider = self.provider
        logger.info("Calling model provider=%s (chat turns=%d)", provider, len(messages))

        if provider == "openai":
            client = self._get_openai()
            if client:
                model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                content = response.choices[0].message.content if response.choices else None
                return content or "No response generated."

        if provider == "bedrock":
            client = self._get_bedrock()
            if client:
                model_id = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")
                system_chunks: List[str] = []
                api_messages: List[Dict[str, Any]] = []
                for m in messages:
                    role = m.get("role", "")
                    content = m.get("content", "")
                    if role == "system":
                        system_chunks.append(content)
                    elif role in ("user", "assistant"):
                        api_messages.append(
                            {
                                "role": role,
                                "content": [{"type": "text", "text": content}],
                            }
                        )
                body_obj: Dict[str, Any] = {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "messages": api_messages,
                }
                if system_chunks:
                    body_obj["system"] = "\n\n".join(system_chunks)
                body = json.dumps(body_obj)
                response = client.invoke_model(modelId=model_id, body=body)
                payload = json.loads(response["body"].read())
                text_blocks = payload.get("content", [])
                text = "\n".join(block.get("text", "") for block in text_blocks if block.get("type") == "text")
                return text or "No response generated."

        last_user = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
        return self._fallback_text(last_user)

    def analyze_scenario(
        self,
        raw_text: str,
        mode_key: str,
        source_name: str = "",
        *,
        use_llm: bool = True,
    ) -> Dict[str, Any]:
        def with_defaults(payload: Dict[str, Any]) -> Dict[str, Any]:
            out = {
                "title": "",
                "summary": "",
                "stakeholders": {"buyer": "", "seller": ""},
                "pain_points": [],
                "risks": [],
                "power_dynamics": [],
                "key_points": [],
                "negotiation_points": [],
                "recommended_strategies": [],
                "tactical_suggestions": [],
                "possible_objections": [],
                "generated_scenario": "",
            }
            out.update(payload)
            return out

        cleaned = raw_text.strip()
        if not cleaned:
            return with_defaults({
                "title": source_name or "Untitled Scenario",
                "summary": "No scenario content was provided.",
            })

        if not use_llm:
            return with_defaults({
                "title": source_name or self._derive_title(cleaned),
                "summary": self._fallback_summary(cleaned),
                "key_points": self._fallback_key_points(cleaned),
                "negotiation_points": self._fallback_negotiation_points(cleaned),
            })

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
            if isinstance(parsed, dict):
                parsed.setdefault("title", source_name or self._derive_title(cleaned))
                parsed.setdefault("summary", self._fallback_summary(cleaned))
                parsed.setdefault("key_points", self._fallback_key_points(cleaned))
                parsed.setdefault("negotiation_points", self._fallback_negotiation_points(cleaned))
                parsed.setdefault("generated_scenario", "")
                return with_defaults(parsed)

        return with_defaults({
            "title": source_name or self._derive_title(cleaned),
            "summary": self._fallback_summary(cleaned),
            "key_points": self._fallback_key_points(cleaned),
            "negotiation_points": self._fallback_negotiation_points(cleaned),
        })

    def create_scenario(self, brief: str, mode_key: str, *, use_llm: bool = True) -> Dict[str, Any]:
        prompt_brief = brief.strip() or "Create a realistic B2B chemical negotiation scenario involving price pressure, payment terms, technical support, and competitor pressure."
        if not use_llm:
            generated = self._fallback_generated_scenario(prompt_brief)
            analysis = self.analyze_scenario(generated, mode_key, "AI Generated Scenario", use_llm=False)
            analysis["generated_scenario"] = generated
            return analysis

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
        analysis = self.analyze_scenario(generated, mode_key, "AI Generated Scenario", use_llm=True)
        analysis["generated_scenario"] = generated
        return analysis

    def _analysis_to_simulation_context(self, analysis: Dict[str, Any]) -> str:
        parts: List[str] = []
        if analysis.get("title"):
            parts.append(f"Title: {analysis['title']}")
        if analysis.get("summary"):
            parts.append(f"Summary: {analysis['summary']}")
        kp = analysis.get("key_points") or []
        if kp:
            parts.append("Key points: " + "; ".join(str(x) for x in kp))
        np_ = analysis.get("negotiation_points") or []
        if np_:
            parts.append("Negotiation focus: " + "; ".join(str(x) for x in np_))
        gs = (analysis.get("generated_scenario") or "").strip()
        if gs:
            parts.append(f"Scenario narrative:\n{gs[:8000]}")
        return "\n\n".join(parts) if parts else "Generic B2B chemical supply negotiation."

    def mentor_analyze_demo_turn(
        self,
        *,
        speaker_label: str,
        utterance: str,
        analysis: Dict[str, Any],
        recent_dialogue: str,
    ) -> str:
        """
        Second-pass mentor commentary on one AI buyer/sales line in Sandbox DEMO.
        """
        ctx = self._analysis_to_simulation_context(analysis)
        prompt = build_demo_turn_mentor_prompt(
            speaker_label=speaker_label,
            utterance=utterance,
            scenario_context=ctx,
            recent_dialogue=recent_dialogue,
            max_words=MENTOR_MAX_WORDS,
        )
        if self.provider not in {"openai", "bedrock"}:
            return fallback_demo_mentor_note(speaker_label, utterance)
        approx_tokens = min(400, max(120, int(MENTOR_MAX_WORDS * 2.2)))
        text = self.complete(prompt, temperature=0.28, max_tokens=approx_tokens)
        normalized = normalize_mentor_text(text or "")
        return normalized if normalized.strip() else fallback_demo_mentor_note(speaker_label, utterance)

    @staticmethod
    def _clean_sim_utterance(raw: str) -> str:
        text = (raw or "").strip()
        for prefix in (
            "Buyer:",
            "Sales:",
            "Seller:",
            "Customer:",
            "Covestro sales:",
            "Covestro Sales:",
            "AI Buyer:",
            "AI Sales:",
        ):
            if text.lower().startswith(prefix.lower()):
                text = text[len(prefix) :].strip()
        return text[:2500]

    @staticmethod
    def _public_transcript_to_text(public_transcript: List[Dict[str, str]], *, max_lines: int = 12) -> str:
        """Render shared public transcript (no private context)."""
        if not public_transcript:
            return "(No spoken turns yet.)"
        lines: List[str] = []
        for item in public_transcript[-max_lines:]:
            speaker = "Buyer" if item.get("speaker") == "buyer" else "Covestro sales"
            lines.append(f"{speaker}: {str(item.get('text', '')).strip()}")
        return "\n".join(lines)

    @staticmethod
    def _private_context_to_text(private_ctx: Dict[str, Any]) -> str:
        goals = [str(x) for x in (private_ctx.get("goals") or [])]
        limits = [str(x) for x in (private_ctx.get("limits") or [])]
        notes = str(private_ctx.get("private_notes") or "").strip()
        parts: List[str] = []
        if goals:
            parts.append("Goals:\n- " + "\n- ".join(goals[:6]))
        if limits:
            parts.append("Limits:\n- " + "\n- ".join(limits[:6]))
        if notes:
            parts.append(f"Private notes:\n{notes[:800]}")
        return "\n\n".join(parts) if parts else "(No private directives.)"

    def build_buyer_messages(self, analysis: Dict[str, Any], simulation_state: Dict[str, Any]) -> List[Dict[str, str]]:
        """Build chat messages for the buyer agent only."""
        context_text = self._analysis_to_simulation_context(analysis)
        public_transcript = simulation_state.get("public_transcript") or []
        buyer_private = simulation_state.get("buyer_private_context") or {}
        system = (
            f"{SYSTEM_FOUNDATION}\n\n"
            "You are the BUYER/CUSTOMER in a B2B chemicals negotiation.\n"
            "Push for commercial advantage while staying realistic and consistent with scenario facts.\n\n"
            "Shared scenario context:\n"
            f"{context_text}\n\n"
            "Your private strategy (do NOT reveal explicitly):\n"
            f"{self._private_context_to_text(buyer_private)}\n\n"
            "Public transcript so far:\n"
            f"{self._public_transcript_to_text(public_transcript)}\n\n"
            "Respond with exactly ONE natural spoken line. No role labels, no bullets, no meta commentary."
        )
        return [{"role": "system", "content": system}, {"role": "user", "content": "Continue the negotiation as buyer."}]

    def build_seller_messages(self, analysis: Dict[str, Any], simulation_state: Dict[str, Any]) -> List[Dict[str, str]]:
        """Build chat messages for the seller agent only."""
        context_text = self._analysis_to_simulation_context(analysis)
        public_transcript = simulation_state.get("public_transcript") or []
        seller_private = simulation_state.get("seller_private_context") or {}
        system = (
            f"{SYSTEM_FOUNDATION}\n\n"
            "You are the COVESTRO B2B SELLER in a chemicals negotiation.\n"
            "Defend value and margin discipline while staying natural and persuasive.\n\n"
            "Shared scenario context:\n"
            f"{context_text}\n\n"
            "Your private strategy (do NOT reveal explicitly):\n"
            f"{self._private_context_to_text(seller_private)}\n\n"
            "Public transcript so far:\n"
            f"{self._public_transcript_to_text(public_transcript)}\n\n"
            "Respond with exactly ONE natural spoken line. No role labels, no bullets, no meta commentary."
        )
        return [{"role": "system", "content": system}, {"role": "user", "content": "Continue the negotiation as seller."}]

    def generate_buyer_line(self, analysis: Dict[str, Any], simulation_state: Dict[str, Any]) -> str:
        """Generate one buyer line from two-agent state."""
        messages = self.build_buyer_messages(analysis, simulation_state)
        text = self.complete_chat(messages, temperature=0.45, max_tokens=520)
        cleaned = self._clean_sim_utterance(text)
        return cleaned or (
            "We still need stronger commercials on price and terms before we can close internal approval."
        )

    def generate_seller_line(self, analysis: Dict[str, Any], simulation_state: Dict[str, Any]) -> str:
        """Generate one seller line from two-agent state."""
        messages = self.build_seller_messages(analysis, simulation_state)
        text = self.complete_chat(messages, temperature=0.4, max_tokens=520)
        cleaned = self._clean_sim_utterance(text)
        return cleaned or (
            "Let’s tie any commercial movement to clear value exchange while keeping payment policy within 45 days."
        )


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

def get_active_model_info() -> Dict[str, str]:
    """
    Human-readable model routing for UI (scenario analysis and chat use the same ModelClient).
    """
    client = ModelClient()
    provider = client.provider
    if provider == "openai":
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        return {
            "provider": provider,
            "label": f"OpenAI — {model}",
            "model_id": model,
        }
    if provider == "bedrock":
        model_id = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")
        return {
            "provider": provider,
            "label": f"Amazon Bedrock — {model_id}",
            "model_id": model_id,
        }
    return {
        "provider": "fallback",
        "label": "Fallback (no API keys configured)",
        "model_id": "",
    }


def scenario_analyzer_display_line(analyzer_mode: str) -> str:
    """
    User-facing line for Step 1: reflects the analyzer dropdown, not only env API keys.
    """
    am = (analyzer_mode or "no_llm").strip().lower()
    if am == "no_llm":
        return "No LLM — heuristic summary only (no API call for scenario analysis)"
    if am == "local_model":
        return "Local analyzer — stub placeholder (no model call yet)"
    cloud = get_active_model_info()["label"]
    return f"Cloud structured analysis — {cloud}"


@lru_cache(maxsize=1)
def get_model_client() -> ModelClient:
    return ModelClient()
