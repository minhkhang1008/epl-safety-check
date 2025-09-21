from __future__ import annotations
from typing import Dict, List, Tuple
import numpy as np
from .league import League

def estimate_probabilities(league: League, sims: int = 20000, seed: int = 12345):
    rng = np.random.default_rng(seed)
    teams = list(league.teams)
    T = len(teams)
    idx = {t:i for i,t in enumerate(teams)}

    stats = league.standings()
    base_pts = np.array([stats[t].points for t in teams], dtype=np.int32)

    rem = league.remaining_fixtures()
    if not rem:
        eps = rng.random(T) * 1e-9
        order = np.argsort(-(base_pts + eps))
        top4 = set(order[:4])
        bottom3 = set(order[-3:])
        prob_top4 = {t: (1.0 if i in top4 else 0.0) for t,i in idx.items()}
        prob_safe = {t: (0.0 if i in bottom3 else 1.0) for t,i in idx.items()}
        return prob_top4, prob_safe

    H = np.array([idx[h] for (h,_) in rem], dtype=np.int32)
    A = np.array([idx[a] for (_,a) in rem], dtype=np.int32)
    M = len(rem)

    pts = np.broadcast_to(base_pts, (sims, T)).copy()

    outcomes = rng.integers(0, 3, size=(sims, M), endpoint=False)

    for k in range(M):
        o = outcomes[:, k]
        h = H[k]; a = A[k]
        hw = (o == 0)
        if hw.any():
            pts[hw, h] += 3
        dr = (o == 1)
        if dr.any():
            pts[dr, h] += 1
            pts[dr, a] += 1
        aw = (o == 2)
        if aw.any():
            pts[aw, a] += 3

    eps = rng.random((sims, T)) * 1e-9
    score = pts + eps
    order = np.argsort(-score, axis=1)

    top4_counts = np.zeros(T, dtype=np.int64)
    safe_counts = np.zeros(T, dtype=np.int64)

    top4 = order[:, :4]
    bottom3 = order[:, -3:]

    for j in range(4):
        top4_counts += np.bincount(top4[:, j], minlength=T)
    bottom_hits = np.zeros(T, dtype=np.int64)
    for j in range(3):
        bottom_hits += np.bincount(bottom3[:, j], minlength=T)
    safe_counts = sims - bottom_hits

    prob_top4 = {teams[i]: top4_counts[i] / sims for i in range(T)}
    prob_safe  = {teams[i]: safe_counts[i] / sims  for i in range(T)}
    return prob_top4, prob_safe
