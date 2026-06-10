"""
World Cup 2026 — match predictor.

Runs the model over all 72 group-stage matches, prints a console table,
and writes a browsable HTML report (worldcup_predictions.html).

Usage:
    python predict_worldcup.py
"""

import html
import sys
from collections import defaultdict

# Windows consoles default to cp1252; force UTF-8 so team names render.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

from schedule import all_group_matches
from model import predict
from data import GROUPS
from simulate import monte_carlo
from value_finder import get_live_bets
from accas import build_accas, build_target_accas, render_html as render_accas
import site_chrome

N_SIMS = 20000   # Monte Carlo tournament runs


def outcome_label(p):
    """Headline outcome + its probability, derived from the predicted scoreline
    so the label and the score never contradict each other."""
    sh, sa = p["score"]
    if sh > sa:
        return f"{p['home']} win", p["p_home"]
    if sa > sh:
        return f"{p['away']} win", p["p_away"]
    return "Draw", p["p_draw"]


def run():
    matches = all_group_matches()
    predictions = [{**m, **predict(m["home"], m["away"], m["host_team"])} for m in matches]

    _print_console(predictions)

    print(f"\nRunning {N_SIMS:,} tournament simulations...")
    sim_results, n = monte_carlo(n=N_SIMS)
    _print_sim_console(sim_results)

    print("\nFetching live Sky Bet odds for accumulators...")
    bets = get_live_bets()
    accas = build_accas(bets) if bets else None
    target_accas = build_target_accas(bets) if bets else None
    if accas:
        print(f"Built {len(accas)} risk tiers + {len(target_accas)} target-return "
              "accas from live odds.")
    else:
        print("No live odds (set ODDS_API_KEY) — acca section skipped.")

    _write_html(predictions, sim_results, n, accas, target_accas)
    print(f"\nWrote worldcup_predictions.html ({len(predictions)} matches + simulation"
          f"{' + accas' if accas else ''}).")
    return predictions, sim_results


def _print_sim_console(res):
    ranked = sorted(res.items(), key=lambda x: x[1]["champion"], reverse=True)
    print(f"\n{'Team':<22}{'Win%':>7}{'Final':>8}{'Semi':>8}{'QF':>8}{'R16':>8}")
    for t, p in ranked[:16]:
        print(f"{t:<22}{p['champion']*100:6.1f}%{p['final']*100:7.1f}%"
              f"{p['semi']*100:7.1f}%{p['quarter']*100:7.1f}%{p['round16']*100:7.1f}%")


# ---------------------------------------------------------------------------
# Console output
# ---------------------------------------------------------------------------
def _print_console(predictions):
    by_group = defaultdict(list)
    for p in predictions:
        by_group[p["group"]].append(p)

    for group in sorted(by_group):
        print(f"\n=== GROUP {group} " + "=" * 40)
        for p in sorted(by_group[group], key=lambda x: x["matchday"]):
            sc = f"{p['score'][0]}-{p['score'][1]}"
            label, prob = outcome_label(p)
            print(
                f"MD{p['matchday']} {p['date']:<10} "
                f"{p['home']:>22} vs {p['away']:<22} "
                f"| {sc}  ({label}, {prob*100:4.0f}%)  "
                f"[H {p['p_home']*100:3.0f} / D {p['p_draw']*100:3.0f} / A {p['p_away']*100:3.0f}]"
            )


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------
def _bar(p_home, p_draw, p_away):
    h, d, a = p_home * 100, p_draw * 100, p_away * 100
    return (
        f'<div class="bar">'
        f'<span class="h" style="width:{h:.1f}%" title="Home {h:.0f}%"></span>'
        f'<span class="d" style="width:{d:.1f}%" title="Draw {d:.0f}%"></span>'
        f'<span class="a" style="width:{a:.1f}%" title="Away {a:.0f}%"></span>'
        f'</div>'
    )


def _sim_section(sim_results, n):
    """Tournament outlook table (title odds from the Monte Carlo)."""
    ranked = sorted(sim_results.items(), key=lambda x: x[1]["champion"], reverse=True)
    rows = [f'<h2>🏆 Tournament Outlook <span class="grpteams">'
            f'{n:,} Monte&nbsp;Carlo simulations</span></h2>',
            '<table>',
            '<tr><th>#</th><th>Team</th><th class="prob">Win title</th>'
            '<th>Final</th><th>Semi</th><th>QF</th><th>R16</th></tr>']
    for i, (team, p) in enumerate(ranked[:20], 1):
        win = p["champion"] * 100
        rows.append(
            f'<tr><td>{i}</td><td class="team">{html.escape(team)}</td>'
            f'<td class="prob"><div class="bar"><span class="h" style="width:{min(win*2,100):.1f}%"></span></div>'
            f'<span class="pct"><b>{win:.1f}%</b></span></td>'
            f'<td>{p["final"]*100:.0f}%</td><td>{p["semi"]*100:.0f}%</td>'
            f'<td>{p["quarter"]*100:.0f}%</td><td>{p["round16"]*100:.0f}%</td></tr>'
        )
    rows.append('</table>')
    return "\n".join(rows)


def _write_html(predictions, sim_results=None, n=0, accas=None, target_accas=None):
    by_group = defaultdict(list)
    for p in predictions:
        by_group[p["group"]].append(p)

    rows = []
    if sim_results:
        rows.append(_sim_section(sim_results, n))
    if accas:
        rows.append(render_accas(accas, target_accas))
    for group in sorted(by_group):
        teams = ", ".join(GROUPS[group])
        rows.append(f'<h2>Group {html.escape(group)} '
                    f'<span class="grpteams">{html.escape(teams)}</span></h2>')
        rows.append('<table>')
        rows.append(
            '<tr><th>MD</th><th>Date</th><th class="r">Home</th>'
            '<th>Score</th><th>Away</th><th>Prediction</th>'
            '<th class="prob">H / D / A</th><th class="venue">Venue</th></tr>'
        )
        for p in sorted(by_group[group], key=lambda x: (x["matchday"], x["home"])):
            label, prob = outcome_label(p)
            sc = f"{p['score'][0]}&ndash;{p['score'][1]}"
            host_tag = ' <span class="host">(H)</span>'
            home = html.escape(p["home"]) + (host_tag if p["host_team"] == p["home"] else "")
            away = html.escape(p["away"]) + (host_tag if p["host_team"] == p["away"] else "")
            rows.append(
                f'<tr>'
                f'<td>{p["matchday"]}</td>'
                f'<td class="date">{html.escape(p["date"])}</td>'
                f'<td class="r team">{home}</td>'
                f'<td class="score">{sc}</td>'
                f'<td class="team">{away}</td>'
                f'<td class="pred">{html.escape(label)} '
                f'<b>{prob*100:.0f}%</b></td>'
                f'<td class="prob">{_bar(p["p_home"], p["p_draw"], p["p_away"])}'
                f'<span class="pct">{p["p_home"]*100:.0f} / {p["p_draw"]*100:.0f} / {p["p_away"]*100:.0f}</span></td>'
                f'<td class="venue">{html.escape(p["venue"])}</td>'
                f'</tr>'
            )
        rows.append('</table>')

    body = "\n".join(rows)
    doc = (_HTML_TEMPLATE.replace("{{BODY}}", body)
           .replace("{{NAV}}", site_chrome.nav("predictions")))
    with open("worldcup_predictions.html", "w", encoding="utf-8") as f:
        f.write(doc)


_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>World Cup 2026 — Match Predictions</title>
<style>
  :root { --h:#2a9d8f; --d:#e9c46a; --a:#e76f51; --ink:#1d3557; --line:#e3e8ef; }
  * { box-sizing:border-box; }
  body { font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
         margin:0; background:#f6f8fb; color:#22303f; line-height:1.45; }
  header { background:linear-gradient(135deg,#1d3557,#2a9d8f); color:#fff; padding:32px 24px; }
  header h1 { margin:0 0 6px; font-size:26px; }
  header p  { margin:0; opacity:.9; font-size:14px; }
  .wrap { max-width:1080px; margin:0 auto; padding:24px; }
  .legend { display:flex; gap:18px; flex-wrap:wrap; font-size:13px; margin:18px 0 8px; }
  .legend span b { display:inline-block; width:12px; height:12px; border-radius:3px; margin-right:6px; vertical-align:-1px; }
  h2 { margin:30px 0 8px; color:var(--ink); font-size:19px; border-bottom:2px solid var(--line); padding-bottom:6px; }
  .grpteams { font-weight:400; font-size:13px; color:#6b7a8d; margin-left:8px; }
  table { width:100%; border-collapse:collapse; background:#fff; border-radius:10px; overflow:hidden;
          box-shadow:0 1px 3px rgba(20,40,70,.08); margin-bottom:8px; }
  th,td { padding:9px 10px; font-size:13.5px; border-bottom:1px solid var(--line); text-align:left; }
  th { background:#f0f4f9; color:#46566a; font-weight:600; font-size:12px; text-transform:uppercase; letter-spacing:.03em; }
  tr:last-child td { border-bottom:none; }
  .r { text-align:right; } .team { font-weight:600; }
  .score { text-align:center; font-weight:700; font-size:15px; color:var(--ink); white-space:nowrap; }
  .date,.venue { color:#6b7a8d; font-size:12px; white-space:nowrap; }
  .pred b { color:var(--ink); }
  .host { color:#e76f51; font-size:11px; font-weight:700; }
  .prob { min-width:150px; }
  .bar { display:flex; height:9px; border-radius:5px; overflow:hidden; background:#eee; }
  .bar .h{background:var(--h)} .bar .d{background:var(--d)} .bar .a{background:var(--a)}
  .pct { font-size:11px; color:#6b7a8d; }
  footer { max-width:1080px; margin:0 auto; padding:18px 24px 50px; font-size:12px; color:#8595a6; }
  /* Accumulator cards */
  .acca-note { font-size:12.5px; color:#6b7a8d; background:#fff6e6; border:1px solid #f0e0bb;
               border-radius:8px; padding:10px 12px; margin:6px 0 16px; }
  .acca-sub { margin:22px 0 10px; font-size:15px; color:#46566a; font-weight:600; }
  .acca-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(330px,1fr)); gap:16px; }
  .acca { background:#fff; border-radius:12px; box-shadow:0 1px 4px rgba(20,40,70,.10);
          overflow:hidden; display:flex; flex-direction:column; }
  .acca-head { padding:14px 16px 6px; }
  .acca-head h3 { margin:0; font-size:17px; color:var(--ink); }
  .legcount { font-size:11px; font-weight:600; color:#fff; background:var(--h);
              border-radius:20px; padding:2px 9px; margin-left:6px; vertical-align:2px; }
  .blurb { margin:6px 0 0; font-size:12.5px; color:#6b7a8d; line-height:1.4; }
  table.acca-legs { box-shadow:none; border-radius:0; margin:8px 0 0; table-layout:fixed; }
  table.acca-legs th, table.acca-legs td { padding:6px 16px; font-size:12.5px;
        white-space:normal; overflow-wrap:anywhere; vertical-align:top; }
  table.acca-legs .score { width:42px; white-space:nowrap; }
  .acca-foot { display:grid; grid-template-columns:1fr 1fr; gap:1px; background:var(--line);
               margin-top:auto; border-top:1px solid var(--line); }
  .acca-foot .stat { background:#fff; padding:9px 16px; display:flex;
                     justify-content:space-between; align-items:baseline; }
  .acca-foot .stat.hi { background:#eafaf6; }
  .acca-foot .lbl { font-size:11px; color:#6b7a8d; text-transform:uppercase; letter-spacing:.03em; }
  .acca-foot .val { font-size:16px; font-weight:700; color:var(--ink); }
  .acca-foot .stat.hi .val { color:#2a9d8f; }
</style></head>
<body>
{{NAV}}
<header>
  <h1>⚽ World Cup 2026 — Match Predictions</h1>
  <p>USA · Mexico · Canada &nbsp;|&nbsp; Group stage · 72 matches &nbsp;|&nbsp; Model snapshot: 10 Jun 2026</p>
</header>
<div class="wrap">
  <div class="legend">
    <span><b style="background:var(--h)"></b>Home / left-team win</span>
    <span><b style="background:var(--d)"></b>Draw</span>
    <span><b style="background:var(--a)"></b>Away / right-team win</span>
    <span><b style="background:#e76f51;border-radius:50%"></b>(H) = host on home soil</span>
  </div>
  {{BODY}}
</div>
<footer>
  Predictions from a Poisson&ndash;Elo model blending world-football Elo, bookmaker title odds,
  recent form, injuries and host-field advantage. Matchday&nbsp;1 carries confirmed dates/venues;
  Matchdays&nbsp;2&ndash;3 show the official window. For entertainment &mdash; not betting advice.
</footer>
</body></html>"""


if __name__ == "__main__":
    run()
