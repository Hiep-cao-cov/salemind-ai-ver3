from typing import Any, Dict

from core.agents.auditor import audit_response
from core.agents.supervisor import resolve_action
from modules.module2 import mentor, real_case, reps, sandbox
from core.scenario_analyzer_v2 import analyze_with_cloud_model, analyze_with_local_model


MODE_RUNNERS = {
    "sandbox": sandbox.run,
    "real_case": real_case.run,
    "reps": reps.run,
    "mentor": mentor.run,
}

MODE_PREPARERS = {
    "sandbox": sandbox.prepare_scenario,
    "real_case": real_case.prepare_scenario
   ## "reps": reps.prepare_scenario,
}


def run_chat(mode: str, action: str, payload: Dict[str, str]) -> Dict[str, Any]:
    normalized_action = resolve_action(action, mode)
    runner = MODE_RUNNERS.get(mode, sandbox.run)
    result = runner(normalized_action, payload)
    if not result.get("audit"):
        result["audit"] = audit_response(str(result.get("reply", "")))
    return result


def prepare_mode_context(
    mode: str,
    source_type: str,
    source_name: str,
    raw_text: str,
    *,
    use_llm: bool = True,
) -> Dict[str, Any]:
    preparer = MODE_PREPARERS.get(mode)
    if not preparer:
        raise ValueError(f"Mode {mode} does not support scenario preparation")
    return preparer(source_type, source_name, raw_text, use_llm=use_llm)


def run_sandbox_simulation(analysis: Dict[str, Any], turns: int = 8) -> Dict[str, Any]:
    return sandbox.simulate(analysis, turns=turns)

def prepare_mode_context_v2(
    mode: str,
    source_type: str,
    source_name: str,
    raw_text: str,
    analyzer_mode: str,
):
    analyzer_mode = (analyzer_mode or "no_llm").strip().lower()

    if analyzer_mode == "no_llm":
        return prepare_mode_context(mode, source_type, source_name, raw_text, use_llm=False)

    # For AI source, keep the scenario generation workflow enabled even when
    # cloud model is selected. This ensures the model can create scenario text
    # and return summary/key points in one step (OpenAI/Bedrock path).
    if analyzer_mode == "cloud_model" and source_type == "ai":
        return prepare_mode_context(mode, source_type, source_name, raw_text, use_llm=True)

    if analyzer_mode == "local_model":
        return analyze_with_local_model(
            mode=mode,
            source_type=source_type,
            source_name=source_name,
            raw_text=raw_text,
        )

    return analyze_with_cloud_model(
        mode=mode,
        source_type=source_type,
        source_name=source_name,
        raw_text=raw_text,
    )