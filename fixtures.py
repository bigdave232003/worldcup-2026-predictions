"""
Shared fixtures helper: kickoff times (BST) and UK broadcaster per match.

Kickoff times come live from The Odds API (/scores returns each match's
commence_time in UTC). BST = UTC+1 throughout June/July 2026 (British Summer
Time), so we just add an hour.

UK broadcaster (BBC/ITV) is a manually-maintained map, since the channel split
isn't in any odds feed. Confirmed allocations (per ITV/BBC announcement and UK
TV listings, June 2026) are filled in; anything not yet confirmed returns
"BBC/ITV TBC" rather than a guess.
"""

import json
import os
import unicodedata
import urllib.request
from datetime import datetime, timedelta

from value_finder import load_api_key

API_HOST = "https://api.the-odds-api.com"
SPORT_KEY = "soccer_fifa_world_cup"
BST_OFFSET = timedelta(hours=1)   # June/July 2026 = British Summer Time (UTC+1)


def _norm(name):
    # Strip accents (Curaçao -> curacao, Türkiye -> turkiye) so API spellings and
    # our keys always match, then normalise a couple of known name variants.
    n = "".join(c for c in unicodedata.normalize("NFKD", name)
                if not unicodedata.combining(c))
    n = n.lower().replace("&", "and").strip()
    n = n.replace("turkiye", "turkey").replace("united states", "usa")
    return n


# Confirmed UK broadcaster by match, keyed by frozenset of normalised team names.
# Source: UK TV listings (live-footballontv.com, Sports Mole, Goal, 101GreatGoals),
# cross-checked June 2026. All 24 Matchday-1 games confirmed (BBC One / ITV1 — the
# BBC Two / ITV4 overflow channels only start from Matchday 2). Later rounds TBC.
_CHANNELS = {
    # --- Matchday 1 (all confirmed) ---
    frozenset(["mexico", "south africa"]):              "ITV1",
    frozenset(["south korea", "czech republic"]):       "ITV1",
    frozenset(["canada", "bosnia and herzegovina"]):    "BBC One",
    frozenset(["usa", "paraguay"]):                     "BBC One",
    frozenset(["qatar", "switzerland"]):                "ITV1",
    frozenset(["brazil", "morocco"]):                   "BBC One",
    frozenset(["haiti", "scotland"]):                   "BBC One",
    frozenset(["australia", "turkey"]):                 "ITV1",
    frozenset(["germany", "curacao"]):                 "ITV1",
    frozenset(["netherlands", "japan"]):               "ITV1",
    frozenset(["ivory coast", "ecuador"]):             "BBC One",
    frozenset(["sweden", "tunisia"]):                  "ITV1",
    frozenset(["spain", "cape verde"]):                "ITV1",
    frozenset(["belgium", "egypt"]):                   "BBC One",
    frozenset(["saudi arabia", "uruguay"]):            "ITV1",
    frozenset(["iran", "new zealand"]):                "BBC One",
    frozenset(["france", "senegal"]):                  "BBC One",
    frozenset(["iraq", "norway"]):                     "BBC One",
    frozenset(["argentina", "algeria"]):               "ITV1",
    frozenset(["austria", "jordan"]):                  "BBC One",
    frozenset(["portugal", "dr congo"]):               "BBC One",
    frozenset(["england", "croatia"]):                 "ITV1",
    frozenset(["ghana", "panama"]):                    "ITV1",
    frozenset(["uzbekistan", "colombia"]):             "BBC One",
    # --- Later rounds: confirmed where known ---
    frozenset(["england", "ghana"]):                   "BBC One",
    frozenset(["panama", "england"]):                  "ITV1",
    frozenset(["scotland", "morocco"]):                "ITV1 / STV",
    frozenset(["brazil", "scotland"]):                 "BBC One",
}


def channel_for(home, away):
    return _CHANNELS.get(frozenset([_norm(home), _norm(away)]), "BBC/ITV TBC")


def fetch_fixtures(api_key=None):
    """Return fixtures sorted by kickoff:
       [{home, away, ko_utc(datetime), ko_bst(datetime), completed, channel}].
    """
    api_key = api_key or load_api_key()
    if not api_key:
        return []
    url = f"{API_HOST}/v4/sports/{SPORT_KEY}/scores/?apiKey={api_key}&daysFrom=3"
    req = urllib.request.Request(url, headers={"User-Agent": "wc2026/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        events = json.load(r)

    out = []
    for ev in events:
        ct = ev.get("commence_time")
        if not ct or not ev.get("home_team"):
            continue
        ko_utc = datetime.fromisoformat(ct.replace("Z", "+00:00"))
        out.append({
            "home": ev["home_team"], "away": ev["away_team"],
            "ko_utc": ko_utc, "ko_bst": ko_utc + BST_OFFSET,
            "completed": bool(ev.get("completed")),
            "channel": channel_for(ev["home_team"], ev["away_team"]),
        })
    out.sort(key=lambda x: x["ko_utc"])
    return out


def next_fixture(fixtures, now_utc=None):
    """The earliest not-yet-completed fixture whose kickoff is in the future
    (falls back to the next non-completed one if none are strictly future)."""
    now_utc = now_utc or datetime.now(tz=fixtures[0]["ko_utc"].tzinfo) if fixtures else None
    if not fixtures:
        return None
    upcoming = [f for f in fixtures if not f["completed"] and f["ko_utc"] >= now_utc]
    if upcoming:
        return upcoming[0]
    pending = [f for f in fixtures if not f["completed"]]
    return pending[0] if pending else None


def fmt_bst(dt):
    """e.g. 'Thu 11 Jun, 20:00 BST'."""
    return dt.strftime("%a %d %b, %H:%M") + " BST"
