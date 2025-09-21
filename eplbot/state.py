import json
from typing import List, Dict, Any
from pathlib import Path

DEFAULT_STATE_PATH = Path("league_state.json")

def load_state(path: str = None) -> Dict[str, Any]:
    p = Path(path) if path else DEFAULT_STATE_PATH
    if not p.exists():
        return {"teams": [], "results": []} 
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def save_state(state: Dict[str, Any], path: str = None) -> None:
    p = Path(path) if path else DEFAULT_STATE_PATH
    with open(p, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
