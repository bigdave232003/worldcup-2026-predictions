"""Generate the full 72-match group-stage fixture list.

Matchday 1 gets its real date/venue (from data.MD1_FIXTURES). Matchdays 2 & 3
are produced from the deterministic round-robin template; their exact
date/venue per match wasn't published in scrapeable form the day before
kickoff, so they carry the official matchday window instead.
"""

from data import GROUPS, ROUND_ROBIN, MD1_FIXTURES, MATCHDAY_WINDOW, HOSTS


def all_group_matches():
    """Yield every group-stage match as a dict."""
    matches = []
    for group, teams in GROUPS.items():
        for matchday, pairings in ROUND_ROBIN.items():
            for hi, ai in pairings:
                home, away = teams[hi], teams[ai]
                key = frozenset([home, away])

                if matchday == 1 and key in MD1_FIXTURES:
                    date, venue = MD1_FIXTURES[key]
                else:
                    date, venue = MATCHDAY_WINDOW[matchday], "TBC"

                # A host plays on home soil; treat that team as the home side
                # for field-advantage purposes regardless of fixture ordering.
                host_team = next((t for t in (home, away) if t in HOSTS), None)

                matches.append({
                    "group": group,
                    "matchday": matchday,
                    "date": date,
                    "venue": venue,
                    "home": home,
                    "away": away,
                    "host_team": host_team,
                })
    return matches
