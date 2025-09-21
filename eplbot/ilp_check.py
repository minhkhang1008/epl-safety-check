from typing import Dict, List, Tuple
from .league import League
import pulp

# Tạo biến cho từng trận còn lại: w/d/l nhị phân, mỗi trận đúng 1 kết quả
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
    # Trả về: team -> biểu thức điểm cuối mùa
    now = {t: s.points for t, s in league.standings().items()}
    pts_expr = {t: pulp.LpAffineExpression() for t in league.teams}
    for t in league.teams:
        pts_expr[t] += now[t]
    for (h, a), wvar in W.items():
        dvar = D[(h, a)]
        lvar = L[(h, a)]
        # Home: 3 cho thắng, 1 cho hòa
        pts_expr[h] += 3 * wvar + 1 * dvar
        # Away: home thua (L) nghĩa là away thắng (+3), hòa (+1)
        pts_expr[a] += 3 * lvar + 1 * dvar
    return pts_expr

def _add_match_constraints(problem, rem, W, D, L):
    for key in rem:
        problem += W[key] + D[key] + L[key] == 1, f"one_outcome_{key[0]}_{key[1]}"

def _feasible_eliminate_top4(league: League, team: str) -> bool:
    # Có kịch bản để ≥4 đội khác có điểm >= team (coi hòa điểm là bất lợi cho team)?
    rem, W, D, L = _build_points_vars(league)
    prob = pulp.LpProblem("EliminateTop4", pulp.LpMinimize)
    _add_match_constraints(prob, rem, W, D, L)
    pts = _points_final(league, W, D, L)

    y = {}
    M = 114  # 3*38 điểm là trần an toàn cho Big-M
    for t in league.teams:
        if t == team:
            continue
        y[t] = pulp.LpVariable(f"Y_{t}", lowBound=0, upBound=1, cat=pulp.LpBinary)
        # pts[t] - pts[team] >= -M*(1 - y[t])  => nếu y[t]=1 thì pts[t] >= pts[team] - 0
        prob += pts[t] - pts[team] >= -M * (1 - y[t])

    prob += pulp.lpSum([y[t] for t in league.teams if t != team]) >= 4
    prob += 0  # mục tiêu 0, chỉ cần tính khả thi
    prob.solve(pulp.PULP_CBC_CMD(msg=False))
    return pulp.LpStatus[prob.status] == "Optimal"

def _feasible_relegate(league: League, team: str) -> bool:
    # Có kịch bản để ≥17 đội khác có điểm >= team (coi hòa điểm là bất lợi cho team)?
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
    prob += 0  # mục tiêu 0, chỉ cần tính khả thi
    prob.solve(pulp.PULP_CBC_CMD(msg=False))
    return pulp.LpStatus[prob.status] == "Optimal"

def guaranteed_top4(league: League, team: str) -> bool:
    return not _feasible_eliminate_top4(league, team)

def guaranteed_safe(league: League, team: str) -> bool:
    return not _feasible_relegate(league, team)