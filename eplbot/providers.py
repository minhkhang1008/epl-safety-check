from __future__ import annotations
import os
import requests
from typing import Dict, List, Any, Tuple, Optional
from datetime import datetime

class FootballDataProvider:
    """football-data.org v4
    Docs: https://www.football-data.org/documentation/api
    Auth: header 'X-Auth-Token: <API_KEY>'
    Useful endpoints:
      - /v4/competitions/PL/standings
      - /v4/competitions/PL/matches?season=YYYY&status=FINISHED
    Rate limits (free): 10 req/min for registered key.
    """
    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://api.football-data.org/v4"):
        self.api_key = api_key or os.environ.get("FOOTBALL_DATA_API_KEY")
        if not self.api_key:
            raise RuntimeError("FOOTBALL_DATA_API_KEY not set")
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({"X-Auth-Token": self.api_key})

    def standings(self) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/competitions/PL/standings"
        r = self.session.get(url, timeout=20)
        r.raise_for_status()
        data = r.json()
        # Return list of {team, points, played, gf, ga}
        table = []
        for st in data.get("standings", []):
            if st.get("type") != "TOTAL":
                continue
            for row in st.get("table", []):
                table.append({
                    "team": row["team"]["name"],
                    "points": row["points"],
                    "played": row["playedGames"],
                    "gf": row["goalsFor"],
                    "ga": row["goalsAgainst"],
                    "gd": row["goalDifference"],
                })
        return table

    def finished_matches(self, season: Optional[int] = None) -> List[Dict[str, Any]]:
        params = {"status": "FINISHED"}
        if season:
            params["season"] = season
        url = f"{self.base_url}/competitions/PL/matches"
        r = self.session.get(url, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        matches = []
        for m in data.get("matches", []):
            score = m.get("score", {}).get("fullTime", {})
            hg = score.get("home", 0) or 0
            ag = score.get("away", 0) or 0
            matches.append({
                "utcDate": m.get("utcDate"),
                "home": m["homeTeam"]["name"],
                "away": m["awayTeam"]["name"],
                "hg": int(hg),
                "ag": int(ag),
                "id": m.get("id"),
            })
        return matches

class ApiFootballProvider:
    """API-FOOTBALL (api-sports.io)
    Docs: https://www.api-football.com/documentation-v3
    Auth: header 'x-apisports-key: <API_KEY>'
    Premier League: league=39, season=YYYY
    Useful endpoints:
      - /v3/standings?league=39&season=YYYY
      - /v3/fixtures?league=39&season=YYYY&status=FT
    Free plan typically ~100 req/day; ratelimit ~10 req/min.
    """
    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://v3.football.api-sports.io"):
        self.api_key = api_key or os.environ.get("APIFOOTBALL_API_KEY")
        if not self.api_key:
            raise RuntimeError("APIFOOTBALL_API_KEY not set")
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({"x-apisports-key": self.api_key})

    def standings(self, season: int) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/standings"
        r = self.session.get(url, params={"league": 39, "season": season}, timeout=30)
        r.raise_for_status()
        data = r.json()
        table = []
        # Navigate nested response
        for resp in data.get("response", []):
            for league in [resp.get("league")]:
                for row in league.get("standings", [[]])[0]:
                    team = row["team"]["name"]
                    table.append({
                        "team": team,
                        "points": row["points"],
                        "played": row["all"]["played"],
                        "gf": row["all"]["goals"]["for"],
                        "ga": row["all"]["goals"]["against"],
                        "gd": row["goalsDiff"],
                    })
        return table

    def finished_matches(self, season: int) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/fixtures"
        r = self.session.get(url, params={"league": 39, "season": season, "status": "FT"}, timeout=40)
        r.raise_for_status()
        data = r.json()
        out = []
        for resp in data.get("response", []):
            teams = resp["teams"]
            goals = resp["goals"]
            match = {
                "utcDate": resp.get("fixture", {}).get("date"),
                "home": teams["home"]["name"],
                "away": teams["away"]["name"],
                "hg": int(goals.get("home") or 0),
                "ag": int(goals.get("away") or 0),
                "id": resp.get("fixture", {}).get("id"),
            }
            out.append(match)
        return out
