from __future__ import annotations
from typing import Dict, List, Tuple
import numpy as np
from .league import League

def estimate_probabilities(league: League, sims: int = 20000, seed: int = 12345):
    rng = np.random.default_rng(seed)
    teams = list(league.teams)
    T = len(teams)
    idx = {t:i for i,t in enumerate(teams)}

    # Base points from current standings
    stats = league.standings()
    base_pts = np.array([stats[t].points for t in teams], dtype=np.int32)

    # Remaining fixtures as index pairs
    rem = league.remaining_fixtures()
    if not rem:
        # Season complete: probabilities are deterministic
        # Build ranking with small random tiebreak only if strictly needed
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

    # Pre-allocate totals for sims x teams
    pts = np.broadcast_to(base_pts, (sims, T)).copy()

    # Outcomes: 0=home win, 1=draw, 2=away win
    outcomes = rng.integers(0, 3, size=(sims, M), endpoint=False)

    # Vectorized add per fixture (loop over fixtures, vector over sims)
    for k in range(M):
        o = outcomes[:, k]
        h = H[k]; a = A[k]
        # home win: +3 to home
        hw = (o == 0)
        if hw.any():
            pts[hw, h] += 3
        # draw: +1 to both
        dr = (o == 1)
        if dr.any():
            pts[dr, h] += 1
            pts[dr, a] += 1
        # away win: +3 to away
        aw = (o == 2)
        if aw.any():
            pts[aw, a] += 3

    # Break ties uniformly by adding tiny random noise (keeps fairness & speed)
    eps = rng.random((sims, T)) * 1e-9
    score = pts + eps

    # Sort each simulation once (T=20, so full sort is cheap)
    order = np.argsort(-score, axis=1)

    # Count frequencies
    top4_counts = np.zeros(T, dtype=np.int64)
    safe_counts = np.zeros(T, dtype=np.int64)

    top4 = order[:, :4]
    bottom3 = order[:, -3:]

    # Efficient counting: for each team, check membership in columns
    # Build boolean matrices where rows=simulations, then sum along axis=0
    for j in range(4):
        top4_counts += np.bincount(top4[:, j], minlength=T)
    # Safe if NOT in bottom-3
    bottom_hits = np.zeros(T, dtype=np.int64)
    for j in range(3):
        bottom_hits += np.bincount(bottom3[:, j], minlength=T)
    safe_counts = sims - bottom_hits

    prob_top4 = {teams[i]: top4_counts[i] / sims for i in range(T)}
    prob_safe  = {teams[i]: safe_counts[i] / sims  for i in range(T)}
    return prob_top4, prob_safe
