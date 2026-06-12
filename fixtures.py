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
import urllib.request
from datetime import datetime, timedelta

from value_finder import load_api_key

API_HOST = "https://api.the-odds-api.com"
SPORT_KEY = "soccer_fifa_world_cup"
BST_OFFSET = timedelta(hours=1)   # June/July 2026 = British Summer Time (UTC+1)


def _norm(name):
    return (name.lower().replace("&", "and").replace("ü", "u")
            .replace("türkiye", "turkey").replace("türkiye", "turkey")
            .replace("united states", "usa").strip())


# Confirmed UK broadcaster by match, keyed by frozenset of normalised team names.
# Source: ITV/BBC World Cup 2026 split + UK TV listings (June 2026).
_CHANNELS = {
    frozenset(["mexico", "south africa"]):              "ITV1",
    frozenset(["south korea", "czech republic"]):       "ITV1",
    frozenset(["canada", "bosnia and herzegovina"]):    "BBC One",
    frozenset(["usa", "paraguay"]):                     "BBC One",
    frozenset(["qatar", "switzerland"]):                "ITV1",
    frozenset(["brazil", "morocco"]):                   "BBC One",
    frozenset(["haiti", "scotland"]):                   "BBC One",
    frozenset(["australia", "turkey"]):                 "ITV1",
    # England group games
    frozenset(["england", "croatia"]):                 "ITV1",
    frozenset(["england", "ghana"]):                   "BBC One",
    frozenset(["panama", "england"]):                  "ITV1",
    # Scotland group games
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
