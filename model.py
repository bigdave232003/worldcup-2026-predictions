"""
Prediction model for World Cup 2026.

Approach
--------
1. Each team gets an *effective Elo* = base Elo + form + host bonus - injuries,
   blended slightly toward the bookmakers' implied strength where odds exist.
2. The Elo difference (plus a host-field-advantage term) gives an expected
   goal supremacy, converted to two Poisson goal-rates (lambda_home, lambda_away).
3. A bivariate-Poisson-style scoreline grid gives P(home win) / P(draw) /
   P(away win) and the single most-likely scoreline.

Every knob worth turning lives in the WEIGHTS block below.
"""

import math
from data import TEAMS, HOSTS

# ---------------------------------------------------------------------------
# TUNABLE WEIGHTS
# ---------------------------------------------------------------------------
# Elo gap -> expected goal *margin* (additive, then capped). Calibrated so a
# ~470-point gap (e.g. minnow vs strong side) yields roughly a 3-goal favourite,
# not a 6-0 certainty. Football is high-variance: even big favourites lose.
ELO_PER_GOAL          = 130.0   # Elo points per goal of expected margin.
                                # Higher => mid-tier games closer to a coin-flip
                                # (less favourite-overrating). Big mismatches
                                # still hit MARGIN_CAP, so minnow scorelines hold.
MARGIN_CAP            = 4.0     # cap expected goal supremacy (keeps probs sane)
BASE_GOALS            = 1.35    # average goals per team per game
HOME_FIELD_ELO        = 55.0    # host-nation field advantage (crowd + familiarity)
# Split of the goal supremacy: favourites mostly score MORE, underdogs score a
# bit less. fav coeff > underdog coeff so big mismatches yield 3-0/4-0, not 2-0.
FAV_GOAL_COEFF        = 0.70
DOG_GOAL_COEFF        = 0.40
NEUTRAL_VENUE_ELO     = 0.0     # everyone else plays on neutral ground

# Blend base Elo with FIFA-rank-implied strength (0 = ignore rank, 1 = only rank).
# A second, independent strength signal smooths Elo's noise. (Was title-odds, but
# those conflate single-match strength with title-winning odds and distort weak
# hosts/longshots, so FIFA rank — a true per-match measure — is used instead.)
ODDS_BLEND            = 0.40

# Form & injuries are already in Elo-equivalent points in data.py; scale here.
FORM_WEIGHT           = 1.0
INJURY_WEIGHT         = 1.0

# Scoreline grid + draw inflation (real football has more draws than independent
# Poisson predicts, because goals are mildly negatively correlated).
MAX_GOALS             = 8
DRAW_INFLATION        = 1.08    # >1 nudges probability mass onto the diagonal


# ---------------------------------------------------------------------------
# STRENGTH
# ---------------------------------------------------------------------------
def _rank_implied_elo(fifa_rank):
    """Map a FIFA world-ranking position to an Elo-scale strength signal.

    Unlike tournament *title* odds (which conflate single-match strength with
    the chance of winning 7 knockout games, and so unfairly punish weak hosts
    and longshots), FIFA rank is a per-team match-strength measure available for
    every side. Linear in rank, anchored to the field's Elo spread: rank 1 maps
    near the top, rank ~85 near the bottom.
    """
    if not fifa_rank:
        return None
    return RANK1_ELO - (fifa_rank - 1) * RANK_ELO_SLOPE


# Anchors for the rank->Elo map (calibrated to this field's Elo range).
RANK1_ELO       = 2150.0
RANK_ELO_SLOPE  = 8.3      # Elo points lost per ranking place

_MEAN_ELO = sum(t["elo"] for t in TEAMS.values()) / len(TEAMS)


def effective_elo(team):
    """Base Elo blended with FIFA-rank strength, plus form and injuries
    (venue handled separately). The blend is symmetric across all teams, so it
    smooths rather than distorts."""
    t = TEAMS[team]
    elo = float(t["elo"])

    rank_elo = _rank_implied_elo(t.get("fifa"))
    if rank_elo is not None:
        elo = (1 - ODDS_BLEND) * elo + ODDS_BLEND * rank_elo

    elo += FORM_WEIGHT * t["form"]
    elo -= INJURY_WEIGHT * t["inj"]
    return elo


def _venue_bonus(team, host_on_home_soil):
    if host_on_home_soil and team in HOSTS:
        return HOME_FIELD_ELO
    return NEUTRAL_VENUE_ELO


# ---------------------------------------------------------------------------
# MATCH MODEL
# ---------------------------------------------------------------------------
def _poisson_pmf(k, lam):
    return math.exp(-lam) * lam**k / math.factorial(k)


def expected_goals(home, away, host_team=None):
    """Return (lambda_home, lambda_away) expected goals.

    host_team: the team (if any) playing on its own soil for this fixture, so
    it receives HOME_FIELD_ELO. None => fully neutral venue.
    """
    eh = effective_elo(home) + _venue_bonus(home, home == host_team)
    ea = effective_elo(away) + _venue_bonus(away, away == host_team)

    supremacy = (eh - ea) / ELO_PER_GOAL          # expected goal margin
    # Cap the margin so extreme Elo gaps don't produce 8-0 certainties.
    supremacy = max(-MARGIN_CAP, min(MARGIN_CAP, supremacy))
    # Split additively: the favourite's rate climbs faster than the underdog's
    # falls, so genuine mismatches produce big scorelines (4-0, 5-0) while even
    # games stay near the base rate. coeffs depend on sign of supremacy so the
    # *favourite* (whichever side) always gets the steeper coefficient.
    if supremacy >= 0:
        lam_home = BASE_GOALS + FAV_GOAL_COEFF * supremacy
        lam_away = BASE_GOALS - DOG_GOAL_COEFF * supremacy
    else:
        lam_home = BASE_GOALS + DOG_GOAL_COEFF * supremacy
        lam_away = BASE_GOALS - FAV_GOAL_COEFF * supremacy
    return max(0.20, lam_home), max(0.20, lam_away)


def predict(home, away, host_team=None):
    """Full prediction for one match.

    Returns dict with outcome probabilities and the most-likely scoreline.
    """
    lam_h, lam_a = expected_goals(home, away, host_team)

    ph = [_poisson_pmf(i, lam_h) for i in range(MAX_GOALS + 1)]
    pa = [_poisson_pmf(j, lam_a) for j in range(MAX_GOALS + 1)]

    grid = {}
    total = 0.0
    for i in range(MAX_GOALS + 1):
        for j in range(MAX_GOALS + 1):
            p = ph[i] * pa[j]
            if i == j:
                p *= DRAW_INFLATION            # mild draw boost
            grid[(i, j)] = p
            total += p

    # renormalise after draw inflation + truncation
    for k in grid:
        grid[k] /= total

    p_home = sum(p for (i, j), p in grid.items() if i > j)
    p_draw = sum(p for (i, j), p in grid.items() if i == j)
    p_away = sum(p for (i, j), p in grid.items() if i < j)

    # Predicted scoreline = rounded expected goals. The single most-likely grid
    # cell of two independent Poissons is always (floor lam_h, floor lam_a),
    # which forces a clean sheet every game and never a draw. Rounding the
    # expected goals instead gives the intuitive "predicted score": draws emerge
    # when the rates are close, clean sheets only in genuine mismatches.
    likely_score = (int(lam_h + 0.5), int(lam_a + 0.5))

    return {
        "home": home,
        "away": away,
        "host_team": host_team,
        "lambda_home": lam_h,
        "lambda_away": lam_a,
        "p_home": p_home,
        "p_draw": p_draw,
        "p_away": p_away,
        "score": likely_score,
        "score_prob": grid[likely_score],
    }
