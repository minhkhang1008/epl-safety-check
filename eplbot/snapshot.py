from __future__ import annotations
from typing import Dict, Any
from .league import League
from .ilp_check import guaranteed_top4, guaranteed_safe
from .sim import estimate_probabilities
import time, json, hashlib

def build_snapshot(L: League, sims: int = 20000, seed: int = 12345) -> Dict[str, Any]:
    flags_top4 = {t: guaranteed_top4(L, t) for t in L.teams}
    flags_safe = {t: guaranteed_safe(L, t) for t in L.teams}
    probs_top4, probs_safe = estimate_probabilities(L, sims=sims, seed=seed)

    table_rows = []
    for i, s in enumerate(L.table_view(), start=1):
        table_rows.append({
            "rank": i,
            "team": s.team,
            "played": s.played, "wins": s.wins, "draws": s.draws, "losses": s.losses,
            "gf": s.gf, "ga": s.ga, "gd": s.gd, "points": s.points,
            "official": {"top4": flags_top4.get(s.team, False), "safe": flags_safe.get(s.team, False)},
            "probTop4": probs_top4.get(s.team, None),
            "probSafe": probs_safe.get(s.team, None),
        })

    m = hashlib.sha256()
    for r in L.results:
        m.update(f'{r["home"]}|{r["away"]}|{r["hg"]}|{r["ag"]}'.encode())

    return {
        "meta": {
            "generated_at": int(time.time()),
            "sims": sims,
            "seed": seed,
            "results_count": len(L.results),
            "teams_count": len(L.teams),
            "fingerprint": m.hexdigest(),
        },
        "table": table_rows,
        "remaining": L.remaining_fixtures(),
    }

def write_snapshot_file(obj: Dict[str, Any], path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
