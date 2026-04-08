import json
from typing import Any, Dict

from core.model_client import get_model_client
from core.prompt_loader import load_prompt_file, render_prompt_template


def _default_result(title: str = "Scenario Analysis") -> Dict[str, Any]:
    return {
        "title": title,
        "summary": "",
        "stakeholders": {
            "buyer": "",
            "seller": "",
        },
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


def analyze_with_cloud_model(
    *,
    mode: str,
    source_type: str,
    source_name: str,
    raw_text: str,
) -> Dict[str, Any]:
    system_prompt = load_prompt_file("scenario_system_cloud.txt")

    if mode == "sandbox":
        user_prompt = render_prompt_template(
            "scenario_user_template_sandbox.txt",
            source_type=source_type,
            source_name=source_name,
            raw_text=raw_text[:12000],
        )
    elif mode == "real_case":
        user_prompt = render_prompt_template(
            "scenario_user_template_real_case.txt",
            source_type=source_type,
            source_name=source_name,
            raw_text=raw_text[:12000],
        )
    else:
        user_prompt = render_prompt_template(
            "scenario_user_template_reps.txt",
            source_type=source_type,
            source_name=source_name,
            raw_text=raw_text[:12000],
        )

    client = get_model_client()
    response_text = client.complete(
        prompt=f"{system_prompt}\n\n{user_prompt}",
        temperature=0.2,
        max_tokens=1400,
    )

    try:
        parsed = json.loads(response_text)
    except Exception:
        result = _default_result(source_name or "Scenario Analysis")
        result["summary"] = response_text[:600]
        result["key_points"] = ["Model response was not valid JSON."]
        result["negotiation_points"] = ["Retry with stricter prompt or inspect output."]
        return result

    result = _default_result(parsed.get("title") or source_name or "Scenario Analysis")
    result.update(parsed)
    return result


def analyze_with_local_model(
    *,
    mode: str,
    source_type: str,
    source_name: str,
    raw_text: str,
) -> Dict[str, Any]:
    return {
        "title": source_name or "Local Model Analyzer",
        "summary": "Local Model is selected, but this analyzer is not implemented yet.",
        "stakeholders": {
            "buyer": "",
            "seller": "",
        },
        "pain_points": [],
        "risks": [],
        "power_dynamics": [],
        "key_points": [
            "Local Model analyzer is currently NULL / pending implementation."
        ],
        "negotiation_points": [],
        "recommended_strategies": [],
        "tactical_suggestions": [],
        "possible_objections": [],
        "generated_scenario": "",
    }