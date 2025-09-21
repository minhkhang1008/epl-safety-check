from __future__ import annotations
from typing import List, Dict, Any, Optional
from .state import load_state, save_state
from .league import League

def merge_finished_matches(L: League, finished: List[Dict[str, Any]], strict_names: bool = True) -> int:
    """Merge finished matches (list of dicts with home,away,hg,ag) into league state.
    Returns number of newly added results.
    """
    existing = set((r["home"], r["away"]) for r in L.results)
    added = 0
    for m in finished:
        key = (m["home"], m["away"])
        if key in existing:
            continue
        if strict_names and (m["home"] not in L.teams or m["away"] not in L.teams):
            continue
        L.submit_result(m["home"], m["away"], m["hg"], m["ag"])
        existing.add(key)
        added += 1
    return added
