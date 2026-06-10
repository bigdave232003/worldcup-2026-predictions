"""
Value-bet finder: compare live Sky Bet odds against the model's probabilities
and surface positive-EV bets + the best-value accumulator.

Data source: The Odds API (https://the-odds-api.com), free tier = 500 req/month.

Setup
-----
1. Get a free key at https://the-odds-api.com/#get-access
2. Provide it either way:
     - set an env var:        export ODDS_API_KEY=xxxxx   (Windows: set ODDS_API_KEY=xxxxx)
     - or create a .env file:  ODDS_API_KEY=xxxxx
3. Run:  python value_finder.py

What it does
------------
- Pulls head-to-head (1X2) odds for all available World Cup matches from Sky Bet.
- Matches each to the model's predicted W/D/L probabilities.
- EV per £1 stake = model_prob * decimal_odds - 1.  EV > 0 => bookie generous.
- Prints all +EV bets, then assembles the highest-combined-EV accumulator.
"""

import json
import os
import sys
import urllib.parse
import urllib.request

from model import predict
from schedule import all_group_matches

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

API_HOST = "https://api.the-odds-api.com"
BOOKMAKER = "skybet"
REGION = "uk"
# Exact sport key for the men's international World Cup match-odds market.
# (Confirmed via /v4/sports — distinct from the Club WC and the outright
# "winner" market soccer_fifa_world_cup_winner.)
WC_SPORT_KEY = "soccer_fifa_world_cup"
MIN_EV = 0.02          # only flag bets at least +2% EV
MAX_ACCA_LEGS = 6      # cap accumulator size


# ---------------------------------------------------------------------------
# API key loading
# ---------------------------------------------------------------------------
def load_api_key():
    key = os.environ.get("ODDS_API_KEY")
    if key:
        return key.strip()
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        for line in open(env_path, encoding="utf-8"):
            line = line.strip()
            if line.startswith("ODDS_API_KEY"):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "wc2026-predictor/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        remaining = r.headers.get("x-requests-remaining")
        data = json.load(r)
    return data, remaining


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------
def resolve_sport_key(api_key):
    """Confirm the men's World Cup key exists and is active (free, no quota)."""
    url = f"{API_HOST}/v4/sports/?apiKey={api_key}&all=true"
    sports, _ = _get(url)
    keys = {s["key"]: s for s in sports}
    if WC_SPORT_KEY in keys:
        if not keys[WC_SPORT_KEY].get("active"):
            print(f"Note: {WC_SPORT_KEY} is listed but not active yet "
                  "(no markets open). Returning it anyway.")
        return WC_SPORT_KEY
    return None


def fetch_odds(api_key, sport_key):
    params = urllib.parse.urlencode({
        "apiKey": api_key, "regions": REGION, "markets": "h2h",
        "oddsFormat": "decimal", "bookmakers": BOOKMAKER,
    })
    url = f"{API_HOST}/v4/sports/{sport_key}/odds/?{params}"
    return _get(url)


# ---------------------------------------------------------------------------
# Matching odds <-> model
# ---------------------------------------------------------------------------
def _model_probs():
    """Map (home, away) -> dict of outcome probabilities from the model."""
    out = {}
    for m in all_group_matches():
        p = predict(m["home"], m["away"], m["host_team"])
        out[(m["home"], m["away"])] = {
            m["home"]: p["p_home"], "Draw": p["p_draw"], m["away"]: p["p_away"],
        }
    return out


def _norm(name):
    return name.lower().replace("&", "and").strip()


def find_value(odds_events):
    model = _model_probs()
    # index model by normalised team-set for order-independent matching
    model_idx = {}
    for (h, a), probs in model.items():
        model_idx[frozenset([_norm(h), _norm(a)])] = (h, a, probs)

    bets = []
    for ev in odds_events:
        home, away = ev.get("home_team"), ev.get("away_team")
        key = frozenset([_norm(home), _norm(away)])
        if key not in model_idx:
            continue
        mh, ma, probs = model_idx[key]
        # Look up probabilities by NORMALISED team name, so the API's home/away
        # ordering (which can differ from our fixture list) never matters.
        prob_by_norm = {_norm(mh): (probs[mh], f"{mh} win"),
                        _norm(ma): (probs[ma], f"{ma} win")}
        for bm in ev.get("bookmakers", []):
            if bm["key"] != BOOKMAKER:
                continue
            for market in bm.get("markets", []):
                if market["key"] != "h2h":
                    continue
                for oc in market["outcomes"]:
                    label = oc["name"]
                    price = oc["price"]
                    if _norm(label) in prob_by_norm:
                        prob, pick = prob_by_norm[_norm(label)]
                    else:
                        prob, pick = probs["Draw"], "Draw"
                    ev_val = prob * price - 1
                    bets.append({
                        "match": f"{mh} v {ma}", "pick": pick,
                        "model_prob": prob, "sky_odds": price, "ev": ev_val,
                    })
    return bets


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
def report(bets):
    value = sorted([b for b in bets if b["ev"] >= MIN_EV],
                   key=lambda x: x["ev"], reverse=True)
    if not value:
        print("No positive-EV bets found at Sky Bet vs the model right now.")
        print("(That's normal — the bookie margin often eats the edge.)")
        return

    print(f"\n=== POSITIVE-EV BETS (Sky Bet vs model, min +{MIN_EV*100:.0f}%) ===")
    print(f"{'pick':<26}{'match':<34}{'sky':>6}{'model%':>8}{'EV':>8}")
    for b in value:
        print(f"{b['pick']:<26}{b['match']:<34}{b['sky_odds']:>6.2f}"
              f"{b['model_prob']*100:>7.0f}%{b['ev']*100:>+7.1f}%")

    # Build best-value acca: take top-EV legs that are also reasonably likely
    # (avoid stacking longshots). Prefer EV but require model_prob >= 0.5.
    legs = [b for b in value if b["model_prob"] >= 0.5][:MAX_ACCA_LEGS]
    if len(legs) >= 2:
        import functools, operator
        odds = functools.reduce(operator.mul, [l["sky_odds"] for l in legs], 1)
        prob = functools.reduce(operator.mul, [l["model_prob"] for l in legs], 1)
        ev = prob * odds - 1
        print(f"\n=== BEST-VALUE ACCUMULATOR ({len(legs)} legs) ===")
        for l in legs:
            print(f"   {l['pick']:<24} @ {l['sky_odds']:.2f}  ({l['match']})")
        print(f"   Combined Sky odds: {odds:.2f}   model prob: {prob*100:.1f}%"
              f"   acca EV: {ev*100:+.1f}%")
        print(f"   £10 stake returns £{odds*10:.2f} if it lands.")


def get_live_bets():
    """Fetch live Sky Bet odds and return the matched bets list, or None if no
    API key / network / data. Used by the HTML report to build accumulators."""
    api_key = load_api_key()
    if not api_key:
        return None
    try:
        sport_key = resolve_sport_key(api_key)
        if not sport_key:
            return None
        events, _ = fetch_odds(api_key, sport_key)
        bets = find_value(events)
        return bets or None
    except Exception as e:
        print(f"(Live odds unavailable: {e})")
        return None


def main():
    api_key = load_api_key()
    if not api_key:
        print("No API key found. Set ODDS_API_KEY env var or create a .env file:")
        print("   ODDS_API_KEY=your_key_here")
        print("Get a free key at https://the-odds-api.com/#get-access")
        sys.exit(1)

    print("Resolving World Cup sport key...")
    sport_key = resolve_sport_key(api_key)
    if not sport_key:
        print("Could not find a World Cup soccer key on The Odds API.")
        print("Run with the /sports endpoint to inspect available keys.")
        sys.exit(1)
    print(f"Using sport key: {sport_key}")

    events, remaining = fetch_odds(api_key, sport_key)
    print(f"Fetched {len(events)} matches from Sky Bet. "
          f"API requests remaining: {remaining}")

    bets = find_value(events)
    report(bets)


if __name__ == "__main__":
    main()
