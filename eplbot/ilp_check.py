from typing import Dict, List, Tuple
from .league import League
import pulp

def _build_points_vars(league: League):
    rem = league.remaining_fixtures()
    W, D, L = {}, {}, {}
    for (h, a) in rem:
        key = (h, a)
        W[key] = pulp.LpVariable(f"W_{h}__{a}", lowBound=0, upBound=1, cat=pulp.LpBinary)
        D[key] = pulp.LpVariable(f"D_{h}__{a}", lowBound=0, upBound=1, cat=pulp.LpBinary)
        L[key] = pulp.LpVariable(f"L_{h}__{a}", lowBound=0, upBound=1, cat=pulp.LpBinary)
    return rem, W, D, L

def _points_final(league: League, W, D, L):
    now = {t: s.points for t, s in league.standings().items()}
    pts_expr = {t: pulp.LpAffineExpression() for t in league.teams}
    for t in league.teams:
        pts_expr[t] += now[t]
    for (h, a), wvar in W.items():
        dvar = D[(h, a)]
        lvar = L[(h, a)]
        pts_expr[h] += 3 * wvar + 1 * dvar
        pts_expr[a] += 3 * lvar + 1 * dvar
    return pts_expr

def _add_match_constraints(problem, rem, W, D, L):
    for key in rem:
        problem += W[key] + D[key] + L[key] == 1, f"one_outcome_{key[0]}_{key[1]}"

def _feasible_eliminate_top4(league: League, team: str) -> bool:
    rem, W, D, L = _build_points_vars(league)
    prob = pulp.LpProblem("EliminateTop4", pulp.LpMinimize)
    _add_match_constraints(prob, rem, W, D, L)
    pts = _points_final(league, W, D, L)

    y = {}
    M = 114  
    for t in league.teams:
        if t == team:
            continue
        y[t] = pulp.LpVariable(f"Y_{t}", lowBound=0, upBound=1, cat=pulp.LpBinary)
        prob += pts[t] - pts[team] >= -M * (1 - y[t])

    prob += pulp.lpSum([y[t] for t in league.teams if t != team]) >= 4
    prob += 0
    prob.solve(pulp.PULP_CBC_CMD(msg=False))
    return pulp.LpStatus[prob.status] == "Optimal"

def _feasible_relegate(league: League, team: str) -> bool:
    rem, W, D, L = _build_points_vars(league)
    prob = pulp.LpProblem("RelegationFeasible", pulp.LpMinimize)
    _add_match_constraints(prob, rem, W, D, L)
    pts = _points_final(league, W, D, L)

    y = {}
    M = 114
    for t in league.teams:
        if t == team:
            continue
        y[t] = pulp.LpVariable(f"Y_{t}", lowBound=0, upBound=1, cat=pulp.LpBinary)
        prob += pts[t] - pts[team] >= -M * (1 - y[t])

    prob += pulp.lpSum([y[t] for t in league.teams if t != team]) >= 17
    prob += 0 
    prob.solve(pulp.PULP_CBC_CMD(msg=False))
    return pulp.LpStatus[prob.status] == "Optimal"

def guaranteed_top4(league: League, team: str) -> bool:
    return not _feasible_eliminate_top4(league, team)

def guaranteed_safe(league: League, team: str) -> bool:
    return not _feasible_relegate(league, team)