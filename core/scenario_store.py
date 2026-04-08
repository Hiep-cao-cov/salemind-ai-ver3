from pathlib import Path
from typing import Dict, List, Optional

SCENARIO_FILE = Path("data/negotiation_scenarios.txt")


def load_scenarios() -> List[Dict[str, str]]:
    if not SCENARIO_FILE.exists():
        return []
    raw = SCENARIO_FILE.read_text(encoding="utf-8", errors="ignore")
    blocks = [block.strip() for block in raw.split("---") if block.strip()]
    scenarios: List[Dict[str, str]] = []
    for block in blocks:
        item: Dict[str, str] = {"id": "", "title": "", "persona": "", "context": ""}
        for line in block.splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            item[key.strip().lower()] = value.strip()
        if item.get("id") and item.get("title") and item.get("context"):
            scenarios.append(item)
    return scenarios


def get_scenario_by_id(scenario_id: str) -> Optional[Dict[str, str]]:
    for scenario in load_scenarios():
        if scenario["id"] == scenario_id:
            return scenario
    return None
