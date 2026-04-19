import json
import os
import re
from functools import lru_cache
from typing import Any, Dict, List, Optional

from utils.logger import get_logger

from core.prompts.demo_mentor_prompt import (
    build_demo_turn_mentor_prompt,
    fallback_demo_mentor_note,
    get_demo_mentor_max_words,
    normalize_mentor_text,
)
from core.prompts.demo_ai_negotiation_prompt import (
    build_demo_ai_negotiation_prompt,
    fallback_demo_script_turns,
)
from core.prompts.real_case_mentor_prompt import (
    build_real_case_mentor_prompt,
    fallback_real_case_mentor_note,
    get_real_case_mentor_max_words,
    normalize_real_case_mentor_text,
)
from core.prompt_loader import (
    get_buy_skill_text,
    get_demo_mentor_rule_text,
    get_real_case_mentor_rule_text,
    get_sell_skill_text,
    get_strategy_policy_text,
)
from utils.ai_output_config import apply_demo_script_hard_word_cap, clamp_demo_turns, get_float, get_int

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
            text = self.complete(
                prompt,
                temperature=get_float("scenario_analyze", "temperature", 0.2),
                max_tokens=get_int("scenario_analyze", "max_tokens", 900),
            )
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
            generated = self.complete(
                prompt,
                temperature=get_float("scenario_create", "temperature", 0.5),
                max_tokens=get_int("scenario_create", "max_tokens", 700),
            )
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

    def _full_negotiation_context(self, analysis: Dict[str, Any]) -> str:
        """Compose dynamic negotiation context only (no static prompt files)."""
        dynamic_ctx = self._analysis_to_simulation_context(analysis).strip()
        return dynamic_ctx or "Generic B2B chemical supply negotiation."

    def mentor_analyze_demo_turn(
        self,
        *,
        speaker_label: str,
        utterance: str,
        analysis: Dict[str, Any],
        recent_dialogue: str,
    ) -> str:
        """
        Second-pass mentor commentary on one AI buyer/sales line in Sandbox DEMO (``demo_mentor_rule.txt`` / [demo_mentor] only).
        """
        ctx = self._analysis_to_simulation_context(analysis)
        try:
            mentor_rules = get_demo_mentor_rule_text()
        except Exception:
            mentor_rules = ""
        mw = get_demo_mentor_max_words()
        prompt = build_demo_turn_mentor_prompt(
            speaker_label=speaker_label,
            utterance=utterance,
            scenario_context=ctx,
            recent_dialogue=recent_dialogue,
            mentor_rules=mentor_rules,
            max_words=mw,
        )
        if self.provider not in {"openai", "bedrock"}:
            return fallback_demo_mentor_note(speaker_label, utterance)
        cap = get_int("demo_mentor", "llm_max_tokens_cap", 400)
        mn = get_int("demo_mentor", "llm_max_tokens_min", 120)
        mult = get_float("demo_mentor", "llm_max_tokens_word_multiplier", 2.2)
        approx_tokens = min(cap, max(mn, int(mw * mult)))
        text = self.complete(
            prompt,
            temperature=get_float("demo_mentor", "llm_temperature", 0.28),
            max_tokens=approx_tokens,
        )
        normalized = normalize_mentor_text(text or "")
        return normalized if normalized.strip() else fallback_demo_mentor_note(speaker_label, utterance)

    def mentor_analyze_real_case_turn(
        self,
        *,
        practice_role: str,
        speaker_label: str,
        utterance: str,
        analysis: Dict[str, Any],
        recent_dialogue: str,
    ) -> str:
        """
        Mentor commentary for Practice (real_case): ``real_case_mentor_rule.txt`` and [real_case_mentor] only—no DEMO mentor assets.
        """
        ctx = self._analysis_to_simulation_context(analysis)
        try:
            mentor_rules = get_real_case_mentor_rule_text()
        except Exception:
            mentor_rules = ""
        pr = str(practice_role or "seller").strip().lower()
        if pr not in ("buyer", "seller"):
            pr = "seller"
        mw = get_real_case_mentor_max_words()
        prompt = build_real_case_mentor_prompt(
            practice_role=pr,
            speaker_label=speaker_label,
            utterance=utterance,
            scenario_context=ctx,
            recent_dialogue=recent_dialogue,
            mentor_rules=mentor_rules,
            max_words=mw,
        )
        if self.provider not in {"openai", "bedrock"}:
            return fallback_real_case_mentor_note(pr, speaker_label, utterance)
        cap = get_int("real_case_mentor", "llm_max_tokens_cap", 900)
        mn = get_int("real_case_mentor", "llm_max_tokens_min", 320)
        mult = get_float("real_case_mentor", "llm_max_tokens_word_multiplier", 2.8)
        approx_tokens = min(cap, max(mn, int(mw * mult)))
        text = self.complete(
            prompt,
            temperature=get_float("real_case_mentor", "llm_temperature", 0.28),
            max_tokens=approx_tokens,
        )
        normalized = normalize_real_case_mentor_text(text or "")
        return (
            normalized
            if normalized.strip()
            else fallback_real_case_mentor_note(pr, speaker_label, utterance)
        )

    def generate_demo_ai_negotiation_script(
        self,
        analysis: Dict[str, Any],
        *,
        turn_count: int = 18,
        difficulty: str = "medium",
    ) -> List[Dict[str, str]]:
        """
        Demo_AI_negotiation: one-shot full transcript (16–20 lines) for Sandbox DEMO replay.
        """
        n = clamp_demo_turns(int(turn_count))
        diff = str(difficulty or "medium").strip().lower()
        if diff not in {"simple", "medium", "hard"}:
            diff = "medium"
        ctx = self._analysis_to_simulation_context(analysis)
        try:
            policy = get_strategy_policy_text()
        except Exception:
            policy = ""
        try:
            sell_ex = get_sell_skill_text()
        except Exception:
            sell_ex = ""
        try:
            buy_ex = get_buy_skill_text()
        except Exception:
            buy_ex = ""

        prompt = build_demo_ai_negotiation_prompt(
            scenario_context=ctx,
            strategy_policy=policy,
            seller_skill_excerpt=sell_ex,
            buyer_skill_excerpt=buy_ex,
            turn_count=n,
            difficulty=diff,
        )

        if self.provider not in {"openai", "bedrock"}:
            return fallback_demo_script_turns(n)

        t_ai = get_float("demo_ai_negotiation", "llm_temperature", 0.42)
        base = get_int("demo_ai_negotiation", "llm_max_tokens_base", 800)
        per = get_int("demo_ai_negotiation", "llm_max_tokens_per_turn", 260)
        cap_tok = get_int("demo_ai_negotiation", "llm_max_tokens_cap", 12000)
        raw = self.complete(
            prompt,
            temperature=t_ai,
            max_tokens=min(cap_tok, base + n * per),
        )
        parsed = self._extract_json(raw)
        turns: Any = None
        if isinstance(parsed, dict):
            turns = parsed.get("turns")
        if not isinstance(turns, list) or len(turns) < max(6, n // 2):
            logger.warning("Demo_AI_negotiation: invalid or short turns; using fallback script")
            return fallback_demo_script_turns(n)
        out = ModelClient._normalize_demo_script_turns(turns, expected=n)
        if len(out) < max(6, n // 2):
            return fallback_demo_script_turns(n)
        return out

    @staticmethod
    def _normalize_demo_script_turns(turns: List[Any], *, expected: int) -> List[Dict[str, str]]:
        out: List[Dict[str, str]] = []
        for i in range(expected):
            row: Any = turns[i] if i < len(turns) else {}
            if not isinstance(row, dict):
                row = {}
            want = "buyer" if i % 2 == 0 else "seller"
            sp = str(row.get("speaker") or "").strip().lower()
            if sp not in ("buyer", "seller"):
                sp = want
            elif sp != want:
                sp = want
            txt = str(row.get("text") or "").strip()
            if not txt:
                txt = (
                    "Let's align on terms that work for both sides while keeping full-package economics explicit."
                )
            txt = apply_demo_script_hard_word_cap(sp, txt)
            out.append({"speaker": sp, "text": txt})
        return out

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
        context_text = self._full_negotiation_context(analysis)
        public_transcript = simulation_state.get("public_transcript") or []
        buyer_private = simulation_state.get("buyer_private_context") or {}
        difficulty = str((simulation_state.get("session_meta") or {}).get("difficulty") or "medium").lower()
        coaching_for_buyer = str(buyer_private.get("coaching_advice_prev") or "").strip()
        try:
            buy_skill_text = get_buy_skill_text().strip()
        except Exception:
            buy_skill_text = ""
        buyer_bias = (
            "Bias: seek practical convergence and close when terms are reasonably aligned.\n"
            "In SIMPLE mode, avoid repeated confirmation loops; ask at most one concise clarification question, then move toward closure.\n\n"
            if difficulty == "simple"
            else "Bias: keep balanced pressure while exploring room for agreement.\n\n"
            if difficulty == "medium"
            else "Bias: maintain a tougher stance, require stronger proof before concessions.\n\n"
        )
        is_opening = not public_transcript
        if is_opening:
            task_block = (
                "OPENING TURN (you speak first—the public transcript is still empty):\n"
                "Deliver ONE natural opening line as the buyer starting the meeting/call.\n"
                "- You may use at most one short acknowledgement of the meeting or time if it fits (e.g. 'Thanks for making time'); then move straight to substance.\n"
                "- Do not stack gratitude or formal filler: avoid repeated 'I appreciate', 'thank you so much', layered pleasantries, or consultant-speak.\n"
                "- Anchor the line in the scenario: state your main commercial pressure, scope, or request (price/ESG/volume/terms/timeline) as appropriate.\n"
                "Sound like a real B2B procurement conversation—direct and professional.\n"
                "Output only natural spoken dialogue (one or two short sentences maximum). "
                "You may include one sharp commercial question if it fits without sounding like generic small talk.\n"
            )
            user_content = "Opening turn: you speak first as buyer. Deliver your line."
        else:
            task_block = "Task instruction: ask at least one clarifying question and output only natural spoken dialogue."
            user_content = "Continue the negotiation as buyer."
        system = (
            "You are the BUYER/CUSTOMER in a B2B chemicals negotiation.\n"
            "Push for commercial advantage while staying realistic and consistent with scenario facts.\n\n"
            "Buyer skill reference:\n"
            f"{buy_skill_text or '(Use disciplined buying tactics with realistic pressure and clarifying questions.)'}\n\n"
            f"Negotiation difficulty: {difficulty.upper()}.\n"
            f"{buyer_bias}"
            "Shared scenario context:\n"
            f"{context_text}\n\n"
            "Your private strategy (do NOT reveal explicitly):\n"
            f"{self._private_context_to_text(buyer_private)}\n\n"
            "Public transcript so far:\n"
            f"{self._public_transcript_to_text(public_transcript, max_lines=20)}\n\n"
            "Coaching recommendation for this turn:\n"
            f"{coaching_for_buyer or '(No previous advice)'}\n\n"
            f"{task_block}"
        )
        return [{"role": "system", "content": system}, {"role": "user", "content": user_content}]

    def build_seller_messages(self, analysis: Dict[str, Any], simulation_state: Dict[str, Any]) -> List[Dict[str, str]]:
        """Build chat messages for the seller agent only."""
        context_text = self._full_negotiation_context(analysis)
        public_transcript = simulation_state.get("public_transcript") or []
        seller_private = simulation_state.get("seller_private_context") or {}
        difficulty = str((simulation_state.get("session_meta") or {}).get("difficulty") or "medium").lower()
        coaching_advice_prev = str(seller_private.get("coaching_advice_prev") or "").strip()
        try:
            sell_skill_text = get_sell_skill_text().strip()
        except Exception:
            sell_skill_text = ""
        seller_bias = (
            "Bias: aim for practical convergence and propose close-ready packaging.\n\n"
            if difficulty == "simple"
            else "Bias: keep firm value defense with selective flexibility.\n\n"
            if difficulty == "medium"
            else "Bias: keep a strict stance and avoid easy concessions unless high reciprocity is offered.\n\n"
        )
        system = (
            "You are the COVESTRO B2B SELLER in a chemicals negotiation.\n"
            "Defend value and margin discipline while staying natural and persuasive.\n\n"
            "Shared scenario context:\n"
            f"{context_text}\n\n"
            "Seller skill reference:\n"
            f"{sell_skill_text or '(Use value-based sales discipline and reciprocal concession logic.)'}\n\n"
            f"Negotiation difficulty: {difficulty.upper()}.\n"
            f"{seller_bias}"
            "Your private strategy (do NOT reveal explicitly):\n"
            f"{self._private_context_to_text(seller_private)}\n\n"
            "Public transcript so far:\n"
            f"{self._public_transcript_to_text(public_transcript, max_lines=20)}\n\n"
            "Previous coaching advice to apply (if present):\n"
            f"{coaching_advice_prev or '(No previous advice)'}\n\n"
            "Respond with exactly ONE natural spoken line. No role labels, no bullets, no meta commentary."
        )
        return [{"role": "system", "content": system}, {"role": "user", "content": "Continue the negotiation as seller."}]

    def generate_buyer_line(self, analysis: Dict[str, Any], simulation_state: Dict[str, Any]) -> str:
        """Generate one buyer line from two-agent state."""
        messages = self.build_buyer_messages(analysis, simulation_state)
        text = self.complete_chat(
            messages,
            temperature=get_float("buyer_agent", "chat_temperature", 0.45),
            max_tokens=get_int("buyer_agent", "chat_max_tokens", 520),
        )
        cleaned = self._clean_sim_utterance(text)
        return cleaned or (
            "We still need stronger commercials on price and terms before we can close internal approval."
        )

    def generate_seller_line(self, analysis: Dict[str, Any], simulation_state: Dict[str, Any]) -> str:
        """Generate one seller draft line from two-agent state."""
        messages = self.build_seller_messages(analysis, simulation_state)
        text = self.complete_chat(
            messages,
            temperature=get_float("seller_agent", "chat_temperature", 0.4),
            max_tokens=get_int("seller_agent", "chat_max_tokens", 520),
        )
        cleaned = self._clean_sim_utterance(text)
        return cleaned or (
            "Let’s tie any commercial movement to clear value exchange while keeping payment policy within 45 days."
        )

    def evaluate_seller_draft(
        self,
        analysis: Dict[str, Any],
        simulation_state: Dict[str, Any],
        draft_response: str,
    ) -> Dict[str, Any]:
        """
        Coaching agent pass/fail review for seller draft.
        """
        context_text = self._full_negotiation_context(analysis)
        history_text = self._public_transcript_to_text(simulation_state.get("public_transcript") or [], max_lines=24)
        try:
            seller_skill_text = get_sell_skill_text().strip()
        except Exception:
            seller_skill_text = ""
        prompt = (
            "You are a negotiation coaching evaluator for a B2B seller.\n"
            "Evaluate the seller draft and decide PASS or FAIL.\n\n"
            "Inputs:\n"
            f"- Shared context:\n{context_text}\n\n"
            f"- Full history:\n{history_text}\n\n"
            f"- Seller draft response:\n{draft_response}\n\n"
            "- Seller skill criteria:\n"
            f"{seller_skill_text or 'Protect value, no unstructured discounting, payment term <=45 days, trade concessions only with reciprocity.'}\n\n"
            "Output STRICT JSON with keys:\n"
            '{"verdict":"PASS|FAIL","violations":["R1: ..."],"recommendation":"specific improvement guidance","deadlock_risk":"LOW|MEDIUM|HIGH","adjustment_for_next_turn":"..."}\n'
            "Do not output anything except JSON."
        )
        raw = self.complete(
            prompt,
            temperature=get_float("coaching_evaluator", "temperature", 0.2),
            max_tokens=get_int("coaching_evaluator", "max_tokens", 220),
        )
        return self._normalize_coaching_result(self._extract_json(raw), fallback_recommendation=(
            "Strengthen value defense and keep payment terms within 45 days before conceding anything."
        ))

    def evaluate_buyer_draft(
        self,
        analysis: Dict[str, Any],
        simulation_state: Dict[str, Any],
        draft_response: str,
    ) -> Dict[str, Any]:
        """
        Coaching agent pass/fail review for buyer draft.
        """
        context_text = self._full_negotiation_context(analysis)
        history_text = self._public_transcript_to_text(simulation_state.get("public_transcript") or [], max_lines=24)
        try:
            buyer_skill_text = get_buy_skill_text().strip()
        except Exception:
            buyer_skill_text = ""
        is_opening = not (simulation_state.get("public_transcript") or [])
        opening_eval = (
            "Context: This is the OPENING buyer line (no prior dialogue yet). "
            "PASS if it is scenario-grounded and commercially substantive with a natural B2B tone. "
            "Do not FAIL solely for lacking a clarifying question if the line anchors a concrete request or pressure point. "
            "FAIL if it is only empty pleasantries, generic thanks, or repetitive 'appreciate/thank you so much' filler without substance.\n\n"
            if is_opening
            else ""
        )
        prompt = (
            "You are a negotiation coaching evaluator for a B2B buyer.\n"
            "Evaluate the buyer draft and decide PASS or FAIL.\n\n"
            "Inputs:\n"
            f"- Shared context:\n{context_text}\n\n"
            f"- Full history:\n{history_text}\n\n"
            f"- Buyer draft response:\n{draft_response}\n\n"
            "- Buyer skill criteria:\n"
            f"{buyer_skill_text or 'Stay consistent, ask clear questions, avoid repetitive deadlock loops, and keep realistic negotiation quality.'}\n\n"
            f"{opening_eval}"
            "Output STRICT JSON with keys:\n"
            '{"verdict":"PASS|FAIL","violations":["R1: ..."],"recommendation":"specific improvement guidance","deadlock_risk":"LOW|MEDIUM|HIGH","adjustment_for_next_turn":"..."}\n'
            "Do not output anything except JSON."
        )
        raw = self.complete(
            prompt,
            temperature=get_float("coaching_evaluator", "temperature", 0.2),
            max_tokens=get_int("coaching_evaluator", "max_tokens", 220),
        )
        return self._normalize_coaching_result(self._extract_json(raw), fallback_recommendation=(
            "Keep the buyer position consistent and ask at least one clear clarifying question."
        ))

    @staticmethod
    def _normalize_coaching_result(parsed: Any, *, fallback_recommendation: str) -> Dict[str, Any]:
        if isinstance(parsed, dict):
            verdict = str(parsed.get("verdict") or parsed.get("decision") or "").strip().upper()
            if verdict in {"PASS", "FAIL"}:
                violations_raw = parsed.get("violations") or []
                if isinstance(violations_raw, list):
                    violations = [str(v).strip() for v in violations_raw if str(v).strip()]
                else:
                    text = str(violations_raw).strip()
                    violations = [text] if text else []
                risk = str(parsed.get("deadlock_risk") or "LOW").strip().upper()
                if risk not in {"LOW", "MEDIUM", "HIGH"}:
                    risk = "LOW"
                rec = str(parsed.get("recommendation") or "").strip() or fallback_recommendation
                adjust = str(parsed.get("adjustment_for_next_turn") or "").strip() or rec
                return {
                    "verdict": verdict,
                    "violations": violations,
                    "recommendation": rec,
                    "deadlock_risk": risk,
                    "adjustment_for_next_turn": adjust,
                }
        return {
            "verdict": "FAIL",
            "violations": [],
            "recommendation": fallback_recommendation,
            "deadlock_risk": "LOW",
            "adjustment_for_next_turn": fallback_recommendation,
        }


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
