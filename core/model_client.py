import json
import os
import re
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

from utils.logger import get_logger

from core.prompts.demo_mentor_prompt import (
    MENTOR_MAX_WORDS,
    build_demo_turn_mentor_prompt,
    fallback_demo_mentor_note,
    normalize_mentor_text,
)
from core.prompts.system_prompt import MODE_GUIDANCE, SYSTEM_FOUNDATION

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
        cleaned = raw_text.strip()
        if not cleaned:
            return {
                "title": source_name or "Untitled Scenario",
                "summary": "No scenario content was provided.",
                "key_points": [],
                "negotiation_points": [],
                "generated_scenario": "",
            }

        if not use_llm:
            return {
                "title": source_name or self._derive_title(cleaned),
                "summary": self._fallback_summary(cleaned),
                "key_points": self._fallback_key_points(cleaned),
                "negotiation_points": self._fallback_negotiation_points(cleaned),
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
    def _sim_transcript_tail(transcript: List[Dict[str, str]], max_lines: int = 10) -> str:
        if not transcript:
            return "(Negotiation has not started yet.)"
        lines: List[str] = []
        for item in transcript[-max_lines:]:
            role = item.get("role", "")
            label = "Buyer" if role == "buyer_ai" else "Covestro sales"
            lines.append(f"{label}: {item.get('text', '').strip()}")
        return "\n".join(lines)

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
    def _buyer_opening_cue() -> str:
        return (
            "[Meeting start — Covestro sales has not spoken yet. "
            "You speak first as the buyer, using only scenario facts: needs, pressure, competition, terms.]"
        )

    def _simulation_base_context(self, analysis: Dict[str, Any]) -> str:
        context_text = self._analysis_to_simulation_context(analysis)
        return (
            f"{SYSTEM_FOUNDATION}\n\n"
            f"Mode guidance: {MODE_GUIDANCE.get('sandbox', '')}\n\n"
            f"Scenario context:\n{context_text}\n\n"
            "---\n"
            "Negotiation simulation: reply with exactly one in-character spoken line. "
            "Stay consistent with the scenario; do not invent contradictory facts. "
            "Build on the conversation history; avoid repeating the same question or offer verbatim; advance the discussion. "
            "No role labels in your line, no bullet lists, no meta-commentary."
        )

    def simulate_negotiation_step(
        self,
        analysis: Dict[str, Any],
        api_hist: List[Dict[str, str]],
        *,
        max_turns: int = 18,
    ) -> Optional[Dict[str, Any]]:
        """
        Run exactly one AI-vs-AI turn. api_hist is OpenAI-style user/assistant pairs (even length).
        Returns None when max_turns already completed (no model call).
        """
        max_turns = max(16, min(20, int(max_turns)))
        i = len(api_hist) // 2
        if i >= max_turns:
            return None

        provider = self.provider
        if provider not in {"openai", "bedrock"}:
            return self._simulate_negotiation_step_fallback(analysis, api_hist, max_turns=max_turns)

        base_context = self._simulation_base_context(analysis)
        hist = [dict(x) for x in api_hist]
        is_buyer = i % 2 == 0
        role_block = (
            "\n\nYou are the BUYER / CUSTOMER. "
            "Respond naturally to the latest user message (Covestro sales, or the meeting-start cue)."
            if is_buyer
            else "\n\nYou are the COVESTRO B2B SALES representative. "
            "Respond naturally to the latest user message (what the buyer said). "
            "Apply margin discipline, max 45-day payment, and value-defense from the system rules above."
        )
        system_full = base_context + role_block
        buyer_opening_cue = self._buyer_opening_cue()

        if is_buyer and i == 0:
            hist.append({"role": "user", "content": buyer_opening_cue})
        else:
            hist.append({"role": "user", "content": hist[-1]["content"]})

        chat_messages = [{"role": "system", "content": system_full}] + hist
        reply = self.complete_chat(
            chat_messages,
            temperature=0.45 if is_buyer else 0.4,
            max_tokens=520,
        )
        text_out = self._clean_sim_utterance(reply)
        if is_buyer and not text_out:
            text_out = (
                "We still see a gap on price and payment versus the benchmarks in our brief — "
                "what can you move on while keeping supply dates?"
            )
        if not is_buyer and not text_out:
            text_out = (
                "Before we adjust commercials, let’s confirm launch timing and technical support scope — "
                "then we can structure value without breaking our 45-day payment policy."
            )

        hist.append({"role": "assistant", "content": text_out})
        role = "buyer_ai" if is_buyer else "sales_ai"
        done = (i + 1) >= max_turns
        return {"api_hist": hist, "item": {"role": role, "text": text_out}, "turn_index": i, "done": done}

    def _simulate_negotiation_step_fallback(
        self,
        analysis: Dict[str, Any],
        api_hist: List[Dict[str, str]],
        *,
        max_turns: int,
    ) -> Optional[Dict[str, Any]]:
        i = len(api_hist) // 2
        if i >= max_turns:
            return None
        templates = self._fallback_pair_templates(analysis)
        role, text_out = templates[i % len(templates)]
        hist = [dict(x) for x in api_hist]
        is_buyer = i % 2 == 0
        if is_buyer and i == 0:
            hist.append({"role": "user", "content": self._buyer_opening_cue()})
        else:
            hist.append({"role": "user", "content": hist[-1]["content"]})
        hist.append({"role": "assistant", "content": text_out})
        done = (i + 1) >= max_turns
        return {"api_hist": hist, "item": {"role": role, "text": text_out}, "turn_index": i, "done": done}

    def _fallback_pair_templates(self, analysis: Dict[str, Any]) -> List[Tuple[str, str]]:
        summary = (analysis.get("summary") or "the case facts")[:160]
        point = (analysis.get("negotiation_points") or ["Defend value before price."])[0]
        return [
            (
                "buyer_ai",
                f"We need sharper commercials on this case — price and terms are under internal review given {summary[:80]}…",
            ),
            (
                "sales_ai",
                "Let’s anchor on launch risk and support scope from the scenario before we touch list price — what is the real decision deadline?",
            ),
            (
                "buyer_ai",
                "Competitors are offering faster ramps; we need a credible package on price and payment or we split the award.",
            ),
            (
                "sales_ai",
                "Our strength is supply continuity and technical coverage in your situation — volume without that visibility does not help either side.",
            ),
            (
                "buyer_ai",
                "We still hear 60-day terms elsewhere; help us close the gap without pushing all risk to us.",
            ),
            (
                "sales_ai",
                "We cannot exceed 45-day payment; we can phase deliveries or add service linkage instead of open-ended term stretch.",
            ),
            (
                "buyer_ai",
                "If policy is fixed on payment, what structured movement can you show on service or allocation?",
            ),
            (
                "sales_ai",
                f"We can prioritize technical response and implementation support tied to forecast share — {point}",
            ),
            (
                "buyer_ai",
                "Forecast visibility is possible if the commercial envelope moves within what we outlined in the scenario.",
            ),
            (
                "sales_ai",
                "Then let’s document volume bands and tie service tiers to each band — still within margin and policy guardrails.",
            ),
        ]

    def simulate_negotiation(self, analysis: Dict[str, Any], turns: int = 18) -> List[Dict[str, str]]:
        turns = max(16, min(20, int(turns)))
        if self.provider not in {"openai", "bedrock"}:
            return self._fallback_simulation(analysis, turns)

        transcript: List[Dict[str, str]] = []
        api_hist: List[Dict[str, str]] = []
        for _ in range(turns):
            step = self.simulate_negotiation_step(analysis, api_hist, max_turns=turns)
            if not step:
                break
            api_hist = step["api_hist"]
            transcript.append(step["item"])
        return transcript

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
        turns = max(16, min(20, int(turns)))
        pair_templates = self._fallback_pair_templates(analysis)
        transcript: List[Dict[str, str]] = []
        p = 0
        while len(transcript) < turns:
            role, tmpl = pair_templates[p % len(pair_templates)]
            transcript.append({"role": role, "text": tmpl})
            p += 1
        return transcript[:turns]


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
