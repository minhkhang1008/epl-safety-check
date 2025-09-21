from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Any
import itertools
import random

@dataclass
class TeamStats:
    team: str
    played: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0
    gf: int = 0
    ga: int = 0
    points: int = 0

    @property
    def gd(self) -> int:
        return self.gf - self.ga

def _clean_teams(teams: List[str]) -> List[str]:
    cleaned = []
    seen = set()
    for t in teams:
        t = t.strip()
        if not t or t.startswith("#"):
            continue
        if t in seen:
            raise ValueError(f"Duplicate team name: {t}")
        seen.add(t)
        cleaned.append(t)
    if len(cleaned) != 20:
        raise ValueError(f"Premier League must have exactly 20 teams (got {len(cleaned)}).")
    return cleaned

@dataclass
class League:
    teams: List[str]
    results: List[Dict[str, Any]] = field(default_factory=list)

    @staticmethod
    def from_state(state: Dict[str, Any]) -> "League":
        return League(teams=list(state.get("teams", [])), results=list(state.get("results", [])))

    def to_state(self) -> Dict[str, Any]:
        return {"teams": self.teams, "results": self.results}

    @staticmethod
    def init_from_list(teams: List[str]) -> "League":
        return League(teams=_clean_teams(teams), results=[])

    def has_team(self, name: str) -> bool:
        return name in self.teams

    def _key(self, home: str, away: str) -> Tuple[str,str]:
        return (home, away)

    def remaining_fixtures(self) -> List[Tuple[str,str]]:
        played = set((r["home"], r["away"]) for r in self.results)
        rem = []
        for h in self.teams:
            for a in self.teams:
                if h == a: 
                    continue
                k = (h, a)
                if k not in played:
                    rem.append(k)
        return rem

    def standings(self) -> Dict[str, TeamStats]:
        stats: Dict[str, TeamStats] = {t: TeamStats(team=t) for t in self.teams}
        for r in self.results:
            h,a,hg,ag = r["home"], r["away"], int(r["hg"]), int(r["ag"])
            sh = stats[h]; sa = stats[a]
            sh.played += 1; sa.played += 1
            sh.gf += hg; sh.ga += ag
            sa.gf += ag; sa.ga += hg
            if hg > ag:
                sh.wins += 1; sa.losses += 1
                sh.points += 3
            elif hg < ag:
                sa.wins += 1; sh.losses += 1
                sa.points += 3
            else:
                sh.draws += 1; sa.draws += 1
                sh.points += 1; sa.points += 1
        return stats

    def submit_result(self, home: str, away: str, hg: int, ag: int) -> None:
        if home not in self.teams or away not in self.teams:
            raise ValueError("Unknown team name.")
        if home == away:
            raise ValueError("Home and away cannot be the same team.")
        for r in self.results:
            if r["home"] == home and r["away"] == away:
                raise ValueError("This fixture has already been recorded.")
        self.results.append({"home": home, "away": away, "hg": int(hg), "ag": int(ag)})

    def table_view(self) -> List[TeamStats]:
        stats = self.standings()
        return sorted(stats.values(), key=lambda s: (-s.points, -s.gd, -s.gf, s.team))

    def validate_complete(self) -> bool:
        return len(self.results) == 380

    def copy(self) -> "League":
        return League(teams=list(self.teams), results=[dict(r) for r in self.results])
