"""
Full-tournament Monte Carlo simulation for World Cup 2026.

Pipeline per simulated tournament:
  1. Play all 72 group matches (random scorelines drawn from the model's Poisson
     rates), build the 12 group tables with FIFA tiebreakers.
  2. Take top-2 of each group (24) + the 8 best third-placed teams (ranked
     across all groups) = 32, and slot them via the official Annex C table.
  3. Play the knockout bracket (R32 -> R16 -> QF -> SF -> Final), knockouts
     resolved by the same model with extra-time/penalty coin-flip on draws.
  4. Tally how often each team reaches each stage / wins.

Run thousands of times to get probabilities. The single deterministic
"most-likely" predictions still come from predict_worldcup.py; this adds the
probabilistic tournament outlook the scorelines alone can't give.
"""

import json
import os
import random
from collections import defaultdict

from data import GROUPS, HOSTS
from model import expected_goals

_ANNEX_C = json.load(open(os.path.join(os.path.dirname(__file__), "annex_c.json")))

# Bracket: which match feeds which. R32 slot table (match -> (home_slot, away_slot)).
# Slot codes: "1X"=winner X, "2X"=runner-up X, "3X"=third place X (filled via Annex C).
R32 = {
    73: ("2A", "2B"), 74: ("1E", "T_1E"), 75: ("1F", "2C"), 76: ("1C", "2F"),
    77: ("1I", "T_1I"), 78: ("2E", "2I"), 79: ("1A", "T_1A"), 80: ("1L", "T_1L"),
    81: ("1D", "T_1D"), 82: ("1G", "T_1G"), 83: ("2K", "2L"), 84: ("1H", "2J"),
    85: ("1B", "T_1B"), 86: ("1J", "2H"), 87: ("1K", "T_1K"), 88: ("2D", "2G"),
}
# Later rounds: match -> (winner_of_matchX, winner_of_matchY)
BRACKET = {
    89: (74, 77), 90: (73, 75), 91: (76, 78), 92: (79, 80),
    93: (83, 84), 94: (81, 82), 95: (86, 88), 96: (85, 87),
    97: (89, 90), 98: (93, 94), 99: (91, 92), 100: (95, 96),
    101: (97, 98), 102: (99, 100),
    104: (101, 102),   # final
}
# Slots that receive a best-third-placed team, in Annex C column order.
THIRD_SLOTS = ["1A", "1B", "1D", "1E", "1G", "1I", "1K", "1L"]


# ---------------------------------------------------------------------------
# Match simulation (random scoreline from the model's Poisson rates)
# ---------------------------------------------------------------------------
def _sim_score(home, away, host_team):
    lam_h, lam_a = expected_goals(home, away, host_team)
    return _poisson(lam_h), _poisson(lam_a)


def _poisson(lam):
    # Knuth's algorithm — fine for the small lambdas here.
    L, k, p = pow(2.718281828459045, -lam), 0, 1.0
    while True:
        k += 1
        p *= random.random()
        if p <= L:
            return k - 1


def _host_of(a, b):
    return next((t for t in (a, b) if t in HOSTS), None)


# ---------------------------------------------------------------------------
# Group stage
# ---------------------------------------------------------------------------
def _play_groups():
    """Return (group_result, thirds) where group_result[g] is the ordered
    standings (best first) and thirds is the list of 3rd-placed team records."""
    standings = {}
    thirds = []
    for g, teams in GROUPS.items():
        rec = {t: dict(pts=0, gf=0, ga=0, gd=0) for t in teams}
        pairings = [(0, 1), (2, 3), (0, 2), (3, 1), (0, 3), (1, 2)]
        for hi, ai in pairings:
            h, a = teams[hi], teams[ai]
            sh, sa = _sim_score(h, a, _host_of(h, a))
            rec[h]["gf"] += sh; rec[h]["ga"] += sa
            rec[a]["gf"] += sa; rec[a]["ga"] += sh
            if sh > sa:
                rec[h]["pts"] += 3
            elif sa > sh:
                rec[a]["pts"] += 3
            else:
                rec[h]["pts"] += 1; rec[a]["pts"] += 1
        for t in teams:
            rec[t]["gd"] = rec[t]["gf"] - rec[t]["ga"]
        # FIFA tiebreak (simplified): pts, gd, gf, then random
        order = sorted(teams, key=lambda t: (rec[t]["pts"], rec[t]["gd"],
                                             rec[t]["gf"], random.random()),
                       reverse=True)
        standings[g] = order
        third = order[2]
        thirds.append((g, third, rec[third]))
    return standings, thirds


def _best_eight_thirds(thirds):
    """Rank the 12 third-placed teams, return the 8 qualifying groups (sorted)."""
    ranked = sorted(thirds, key=lambda x: (x[2]["pts"], x[2]["gd"],
                                           x[2]["gf"], random.random()),
                    reverse=True)
    qualified = ranked[:8]
    qual_groups = "".join(sorted(g for g, _, _ in qualified))
    third_team_by_group = {g: t for g, t, _ in qualified}
    return qual_groups, third_team_by_group


# ---------------------------------------------------------------------------
# Knockouts
# ---------------------------------------------------------------------------
def _ko_winner(home, away):
    sh, sa = _sim_score(home, away, _host_of(home, away))
    if sh > sa:
        return home
    if sa > sh:
        return away
    return random.choice([home, away])   # ET/penalties coin-flip


def _run_tournament():
    standings, thirds = _play_groups()
    qual_groups, third_by_group = _best_eight_thirds(thirds)
    annex = _ANNEX_C[qual_groups]        # slot -> "3X"

    # Resolve slot codes to actual teams.
    slot_team = {}
    for g, order in standings.items():
        slot_team[f"1{g}"] = order[0]
        slot_team[f"2{g}"] = order[1]
    # third-place slots
    for slot in THIRD_SLOTS:
        third_group = annex[slot][1]      # "3E" -> "E"
        slot_team[f"T_{slot}"] = third_by_group[third_group]

    # Track how deep each team gets. Encoding: smaller = deeper (1=champion,
    # 2=final, 4=semi, 8=QF, 16=R16, 32=R32). Use min() to keep the deepest.
    reached = {}
    winners = {}

    def mark(team, depth):
        reached[team] = min(reached.get(team, 99), depth)

    # R32
    for m, (hs, as_) in R32.items():
        h, a = slot_team[hs], slot_team[as_]
        mark(h, 32); mark(a, 32)
        winners[m] = _ko_winner(h, a)

    for m in range(89, 97):               # R16
        a, b = BRACKET[m]
        mark(winners[a], 16); mark(winners[b], 16)
        winners[m] = _ko_winner(winners[a], winners[b])
    for m in range(97, 101):              # QF
        a, b = BRACKET[m]
        mark(winners[a], 8); mark(winners[b], 8)
        winners[m] = _ko_winner(winners[a], winners[b])
    for m in (101, 102):                  # SF
        a, b = BRACKET[m]
        mark(winners[a], 4); mark(winners[b], 4)
        winners[m] = _ko_winner(winners[a], winners[b])
    # Final
    fa, fb = winners[101], winners[102]
    mark(fa, 2); mark(fb, 2)
    champ = _ko_winner(fa, fb)
    mark(champ, 1)
    return reached, champ


# ---------------------------------------------------------------------------
# Monte Carlo driver
# ---------------------------------------------------------------------------
def monte_carlo(n=20000, seed=42):
    random.seed(seed)
    # counters: per team, how many times reached each stage threshold
    stages = ["round32", "round16", "quarter", "semi", "final", "champion"]
    thresholds = {"round32": 32, "round16": 16, "quarter": 8,
                  "semi": 4, "final": 2, "champion": 1}
    tally = defaultdict(lambda: dict.fromkeys(stages, 0))

    for _ in range(n):
        reached, champ = _run_tournament()
        for team, depth in reached.items():
            for s in stages:
                if depth <= thresholds[s]:
                    tally[team][s] += 1

    results = {}
    for team, c in tally.items():
        results[team] = {s: c[s] / n for s in stages}
    return results, n


if __name__ == "__main__":
    res, n = monte_carlo()
    ranked = sorted(res.items(), key=lambda x: x[1]["champion"], reverse=True)
    print(f"\nWorld Cup 2026 — {n:,} simulations\n")
    print(f"{'Team':<24}{'Win%':>7}{'Final':>8}{'Semi':>8}{'QF':>8}{'R16':>8}")
    for team, p in ranked[:24]:
        print(f"{team:<24}{p['champion']*100:6.1f}%{p['final']*100:7.1f}%"
              f"{p['semi']*100:7.1f}%{p['quarter']*100:7.1f}%{p['round16']*100:7.1f}%")
