from pathlib import Path

PROMPT_DIR = Path("data/prompts")
LEGACY_PROMPT_DIR = Path("data")


def load_prompt_template(path: str) -> str:
    """Load a prompt template from data paths.

    Supports:
    - absolute paths
    - relative paths like "prompts/foo.txt" or "scenario_system_cloud.txt"
    - compatibility lookup in both data/prompts and data/
    """
    raw = Path(path)
    candidates = []

    if raw.is_absolute():
        candidates.append(raw)
    else:
        candidates.append(raw)
        candidates.append(PROMPT_DIR / raw.name)
        candidates.append(LEGACY_PROMPT_DIR / raw.name)
        if str(raw).startswith("prompts/"):
            candidates.append(LEGACY_PROMPT_DIR / raw)

    for candidate in candidates:
        if candidate.exists():
            return candidate.read_text(encoding="utf-8")
    raise FileNotFoundError(f"Prompt file not found: {path}")


def get_scenario_system_prompt() -> str:
    """Return the cloud scenario-analysis system prompt."""
    return load_prompt_template("scenario_system_cloud.txt")


def get_real_case_analysis_template() -> str:
    """Return the REAL CASE scenario analysis user template."""
    return load_prompt_template("scenario_user_template_real_case.txt")


def get_sandbox_analysis_template() -> str:
    """Return the SANDBOX scenario analysis user template."""
    return load_prompt_template("scenario_user_template_sandbox.txt")

def get_deal_rule_text() -> str:
    """Return sandbox deal-termination rule text."""
    return load_prompt_template("rule_deal.txt")


def load_prompt_file(filename: str) -> str:
    """Backward-compatible wrapper for existing callers."""
    return load_prompt_template(filename)


def render_prompt_template(filename: str, **kwargs) -> str:
    template = load_prompt_template(filename)
    return template.format(**kwargs)