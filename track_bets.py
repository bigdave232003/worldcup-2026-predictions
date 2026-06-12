"""
Bet tracker for the placed accumulators.

Reads the frozen bets from bets.json, fetches live match results from The Odds
API /scores endpoint, evaluates each leg and each acca, and writes a
self-contained tracker page: bet_tracker.html.

Leg status:  won | lost | pending   (a leg "wins" if the picked team won)
Acca status: WON      — every leg won
             LOST     — any leg lost
             LIVE     — no leg lost yet, some still pending

Usage:  python track_bets.py        (re-run any time to refresh results)
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

from value_finder import load_api_key
import site_chrome
from fixtures import (fetch_score_events, fixtures_from_events,
                      fmt_bst, channel_for)

HERE = os.path.dirname(__file__)


def _norm(name):
    return name.lower().replace("&", "and").strip()


# ---------------------------------------------------------------------------
# Fetch results
# ---------------------------------------------------------------------------
def results_from_events(events):
    """Return {frozenset(team_a,team_b): result_dict} for completed matches,
    parsed from raw /scores events (see fixtures.fetch_score_events). Parsing is
    split from fetching so results + fixtures share ONE API call per refresh."""
    results = {}
    for ev in events:
        home, away = ev.get("home_team"), ev.get("away_team")
        if not home or not away:
            continue
        hg = ag = None
        if ev.get("scores"):
            for s in ev["scores"]:
                try:
                    val = int(s["score"])
                except (ValueError, TypeError, KeyError):
                    continue
                if _norm(s["name"]) == _norm(home):
                    hg = val
                elif _norm(s["name"]) == _norm(away):
                    ag = val
        results[frozenset([_norm(home), _norm(away)])] = {
            "home": home, "away": away, "home_goals": hg, "away_goals": ag,
            "completed": bool(ev.get("completed")),
            "commence": ev.get("commence_time", ""),
        }
    return results


# ---------------------------------------------------------------------------
# Evaluate
# ---------------------------------------------------------------------------
def eval_leg(leg, results):
    """Return (status, score_str) for one leg."""
    teams = [t.strip() for t in leg["match"].split(" v ")]
    key = frozenset(_norm(t) for t in teams)
    res = results.get(key)
    if not res or not res["completed"] or res["home_goals"] is None:
        return "pending", "—"

    hg, ag = res["home_goals"], res["away_goals"]
    score = f"{res['home']} {hg}–{ag} {res['away']}"
    # did the picked team win?
    if hg == ag:
        winner = None
    elif hg > ag:
        winner = _norm(res["home"])
    else:
        winner = _norm(res["away"])
    status = "won" if winner == _norm(leg["team"]) else "lost"
    return status, score


def _fixture_lookup(fixtures):
    """Map frozenset(normalised team names) -> fixture dict (time + channel)."""
    return {frozenset([_norm(f["home"]), _norm(f["away"])]): f for f in fixtures}


def eval_acca(acca, results, fix_by_match=None):
    fix_by_match = fix_by_match or {}
    legs = []
    for leg in acca["legs"]:
        status, score = eval_leg(leg, results)
        teams = [t.strip() for t in leg["match"].split(" v ")]
        fx = fix_by_match.get(frozenset(_norm(t) for t in teams))
        legs.append({
            **leg, "status": status, "score": score,
            "ko_bst": fmt_bst(fx["ko_bst"]) if fx else "TBC",
            "ko_utc": fx["ko_utc"] if fx else None,
            "channel": fx["channel"] if fx else channel_for(*teams),
        })
    statuses = [l["status"] for l in legs]
    if "lost" in statuses:
        overall = "LOST"
    elif all(s == "won" for s in statuses):
        overall = "WON"
    else:
        overall = "LIVE"
    won_n = statuses.count("won")
    return {**acca, "legs": legs, "overall": overall,
            "won_legs": won_n, "total_legs": len(legs)}


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------
import html as _html


def _chan_badge(ch):
    cls = "ch-bbc" if "BBC" in ch else ("ch-itv" if "ITV" in ch else "ch-tbc")
    return f'<span class="chan {cls}">{_html.escape(ch)}</span>'


def _leg_row(l, next_key=None):
    icon = {"won": "✅", "lost": "❌", "pending": "⏳"}[l["status"]]
    teams = [t.strip() for t in l["match"].split(" v ")]
    is_next = next_key is not None and frozenset(_norm(t) for t in teams) == next_key
    cls = f'leg-{l["status"]}' + (" leg-next" if is_next else "")
    next_tag = '<span class="nextpill">NEXT</span>' if is_next else ""
    return (f'<tr class="{cls}">'
            f'<td class="st">{icon}</td>'
            f'<td class="team">{_html.escape(l["pick"])}{next_tag}</td>'
            f'<td class="venue">{_html.escape(l["match"])}<br>'
            f'<span class="kowhen">{_html.escape(l["ko_bst"])}</span> '
            f'{_chan_badge(l["channel"])}</td>'
            f'<td class="score">{l["odds"]:.2f}</td>'
            f'<td class="res">{_html.escape(l["score"])}</td></tr>')


def _acca_next_key(a):
    """The next match still to be played WITHIN this acca: the earliest-kickoff
    pending leg. Returns its team-set key, or None if the acca is settled."""
    pending = [l for l in a["legs"] if l["status"] == "pending"]
    if not pending:
        return None
    # earliest by kickoff; legs without a known time sort last (inf sentinel)
    nxt = min(pending, key=lambda l: l["ko_utc"].timestamp()
              if l["ko_utc"] else float("inf"))
    teams = [t.strip() for t in nxt["match"].split(" v ")]
    return frozenset(_norm(t) for t in teams)


def _acca_card(a, next_key=None):
    badge = {"WON": ("badge-won", "WON 🎉"),
             "LOST": ("badge-lost", "LOST"),
             "LIVE": ("badge-live", "STILL LIVE")}[a["overall"]]
    # Highlight each acca's OWN next match (not one global next across all accas),
    # so every live acca shows where it stands.
    own_next = _acca_next_key(a)
    legrows = "\n".join(_leg_row(l, own_next) for l in a["legs"])
    ret = a["returns"]
    ret_str = f"£{ret:,.0f}" if ret >= 1000 else f"£{ret:,.2f}"
    profit = ret - a["stake"]
    if a["overall"] == "WON":
        outcome = f'<span class="profit-win">+£{profit:,.2f} profit</span>'
    elif a["overall"] == "LOST":
        outcome = f'<span class="profit-loss">−£{a["stake"]:.2f} (busted)</span>'
    else:
        outcome = (f'<span class="profit-live">{a["won_legs"]}/{a["total_legs"]} '
                   f'legs in &middot; {ret_str} still to play for</span>')
    return f"""
      <div class="acca {badge[0]}-card">
        <div class="acca-head">
          <h3>{a['emoji']} {_html.escape(a['name'])}
            <span class="badge {badge[0]}">{badge[1]}</span></h3>
          <p class="meta">£{a['stake']:.0f} @ {a['combined_odds']:,.2f} &rarr;
            returns {ret_str} &nbsp;|&nbsp; {outcome}</p>
        </div>
        <table class="legs">
          <tr><th></th><th>Selection</th><th>Match</th><th class="score">Odds</th>
              <th>Result</th></tr>
          {legrows}
        </table>
      </div>"""


def write_tracker(accas, generated, any_results):
    cards = "\n".join(_acca_card(a) for a in accas)
    total_stake = sum(a["stake"] for a in accas)
    won = [a for a in accas if a["overall"] == "WON"]
    total_return = sum(a["returns"] for a in won)
    live = [a for a in accas if a["overall"] == "LIVE"]
    potential = sum(a["returns"] for a in live)

    status_line = (
        f"Staked £{total_stake:.0f} across {len(accas)} accas &middot; "
        f"returned £{total_return:,.2f} so far &middot; "
        f"£{potential:,.2f} still live"
    )
    note = ("" if any_results else
            '<p class="acca-note">No matches have finished yet — kicks off '
            '11 June. Re-run <code>python track_bets.py</code> to refresh results.</p>')

    doc = _TEMPLATE.replace("{{CARDS}}", cards) \
                   .replace("{{STATUS}}", status_line) \
                   .replace("{{GENERATED}}", _html.escape(generated)) \
                   .replace("{{NOTE}}", note) \
                   .replace("{{NAV}}", site_chrome.nav("bets"))
    out = os.path.join(HERE, "bet_tracker.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(doc)
    return out


_TEMPLATE = """<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<!-- Auto-reload every 10 min so an open tab picks up freshly-pushed results. -->
<meta http-equiv="refresh" content="600">
<title>My World Cup 2026 Bets</title>
<style>
  :root { --ink:#1d3557; --line:#e3e8ef; --won:#2a9d8f; --lost:#e76f51; --live:#e9a33a; }
  * { box-sizing:border-box; }
  body { font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
         margin:0; background:#f6f8fb; color:#22303f; }
  header { background:linear-gradient(135deg,#1d3557,#2a9d8f); color:#fff; padding:30px 24px; }
  header h1 { margin:0 0 6px; font-size:24px; }
  header p { margin:0; opacity:.92; font-size:14px; }
  .wrap { max-width:920px; margin:0 auto; padding:24px; }
  .acca-note { font-size:13px; color:#6b7a8d; background:#fff6e6; border:1px solid #f0e0bb;
               border-radius:8px; padding:10px 12px; margin:0 0 18px; }
  code { background:#eef2f7; padding:1px 5px; border-radius:4px; font-size:12px; }
  .acca { background:#fff; border-radius:12px; box-shadow:0 1px 4px rgba(20,40,70,.10);
          margin-bottom:18px; overflow:hidden; border-left:5px solid var(--line); }
  .badge-won-card { border-left-color:var(--won); }
  .badge-lost-card { border-left-color:var(--lost); opacity:.85; }
  .badge-live-card { border-left-color:var(--live); }
  .acca-head { padding:14px 18px 8px; }
  .acca-head h3 { margin:0; font-size:18px; color:var(--ink); }
  .badge { font-size:11px; font-weight:700; color:#fff; border-radius:20px;
           padding:2px 10px; margin-left:8px; vertical-align:2px; letter-spacing:.03em; }
  .badge-won { background:var(--won); } .badge-lost { background:var(--lost); }
  .badge-live { background:var(--live); }
  .meta { margin:7px 0 0; font-size:13px; color:#6b7a8d; }
  .profit-win { color:var(--won); font-weight:700; }
  .profit-loss { color:var(--lost); font-weight:700; }
  .profit-live { color:#46566a; font-weight:600; }
  table.legs { width:100%; border-collapse:collapse; margin-top:6px; table-layout:fixed; }
  table.legs th, table.legs td { padding:8px 18px; font-size:13px; text-align:left;
        border-top:1px solid var(--line); white-space:normal; overflow-wrap:anywhere;
        vertical-align:top; }
  table.legs th { background:#f0f4f9; color:#46566a; font-size:11px;
        text-transform:uppercase; letter-spacing:.03em; border-top:none; }
  .legs .st { width:34px; text-align:center; }
  .legs .score { width:54px; text-align:center; white-space:nowrap; font-weight:600; }
  .legs .team { font-weight:600; }
  .legs .venue { color:#6b7a8d; font-size:12px; }
  .legs .res { color:var(--ink); font-size:12px; }
  tr.leg-won .team { color:var(--won); }
  tr.leg-lost { background:#fdf0ec; }
  tr.leg-lost .team { color:var(--lost); text-decoration:line-through; }
  tr.leg-pending .res { color:#9aa7b6; }
  .legs .kowhen { color:#46566a; font-size:11.5px; font-weight:600; }
  .chan { display:inline-block; font-size:10px; font-weight:700; color:#fff;
    border-radius:12px; padding:1px 7px; vertical-align:1px; }
  .ch-bbc { background:#000; } .ch-itv { background:#d81f7a; } .ch-tbc { background:#9aa7b6; }
  tr.leg-next { background:#eafaf6; box-shadow:inset 3px 0 0 var(--won); }
  .nextpill { background:var(--won); color:#fff; font-size:9px; font-weight:800;
    border-radius:10px; padding:1px 6px; margin-left:7px; vertical-align:1px; letter-spacing:.05em; }
  footer { max-width:920px; margin:0 auto; padding:6px 24px 50px; font-size:12px; color:#8595a6; }
</style></head>
<body>
{{NAV}}
<header>
  <h1>🎟️ My World Cup 2026 Accumulators</h1>
  <p>{{STATUS}}</p>
</header>
<div class="wrap">
  {{NOTE}}
  {{CARDS}}
</div>
<footer>
  Results via The Odds API. Updated: {{GENERATED}}. Re-run <code>python track_bets.py</code> to refresh.
  For entertainment only.
</footer>
</body></html>"""


def main(events=None):
    bets = json.load(open(os.path.join(HERE, "bets.json"), encoding="utf-8"))
    results, fixtures = {}, []
    # `events` may be passed in (refresh.py fetches once and shares); otherwise
    # fetch here. Either way it's a single /scores call.
    if events is None:
        api_key = load_api_key()
        if api_key:
            try:
                events = fetch_score_events(api_key)
            except Exception as e:
                print(f"(Could not fetch results/fixtures: {e})")
                events = []
        else:
            print("No API key — showing bets as pending. Set ODDS_API_KEY to fetch results.")
            events = []
    if events:
        results = results_from_events(events)
        fixtures = fixtures_from_events(events)

    fix_by_match = _fixture_lookup(fixtures)
    evaluated = [eval_acca(a, results, fix_by_match) for a in bets["accas"]]
    any_results = any(l["status"] != "pending" for a in evaluated for l in a["legs"])

    # console summary
    for a in evaluated:
        print(f"{a['emoji']} {a['name']}: {a['overall']} "
              f"({a['won_legs']}/{a['total_legs']} legs won)")
        for l in a["legs"]:
            mark = {"won": "✅", "lost": "❌", "pending": "⏳"}[l["status"]]
            print(f"   {mark} {l['pick']:<22} {l['score']}")

    # generated timestamp: use the API's freshest last_update if available, else a label
    # Real "last refreshed" stamp in BST (UTC+1), so the page shows when the
    # Action/you last pulled results.
    stamp = (datetime.now(timezone.utc) + timedelta(hours=1)).strftime("%a %d %b, %H:%M BST")
    generated = stamp + ("" if any_results else " — pre-tournament, no results yet")
    out = write_tracker(evaluated, generated, any_results)
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
