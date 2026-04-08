from pathlib import Path

PROMPT_DIR = Path("data/prompts")


def load_prompt_file(filename: str) -> str:
    path = PROMPT_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8")


def render_prompt_template(filename: str, **kwargs) -> str:
    template = load_prompt_file(filename)
    return template.format(**kwargs)