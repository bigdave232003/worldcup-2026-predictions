"""
Generate next_game.html — the next match to be played, its BST kickoff, UK
broadcaster, a live countdown, the model's prediction, and the upcoming
fixtures that follow.

Usage:  python next_game.py   (re-run to refresh; also called by build_site.py)
"""

import html as _html
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

import site_chrome
from fixtures import (fetch_score_events, fixtures_from_events,
                      next_fixture, fmt_bst)
from model import predict
from data import HOSTS

HERE = os.path.dirname(os.path.abspath(__file__))


def _norm(n):
    return n.lower().replace("&", "and").replace("ü", "u").replace("united states", "usa").strip()


def _host_of(a, b):
    # match the API's name variants to our model's team keys where they differ
    return next((t for t in (a, b) if _norm(t) in {_norm(h) for h in HOSTS}), None)


# The API uses a few short names; map them to the model's team keys.
_NAME_FIX = {
    "Turkey": "Türkiye", "USA": "United States",
    "Bosnia & Herzegovina": "Bosnia and Herzegovina",
}


def _model_name(n):
    return _NAME_FIX.get(n, n)


def _prediction(home, away):
    """Return (score_str, label, probs) from the model, or None if unknown teams."""
    try:
        p = predict(_model_name(home), _model_name(away), _host_of(home, away))
    except KeyError:
        return None
    sh, sa = p["score"]
    if sh > sa:
        label = f"{home} win"
    elif sa > sh:
        label = f"{away} win"
    else:
        label = "Draw"
    return f"{sh}–{sa}", label, (p["p_home"], p["p_draw"], p["p_away"])


def _channel_badge(ch):
    cls = "ch-bbc" if "BBC" in ch else ("ch-itv" if "ITV" in ch else "ch-tbc")
    return f'<span class="chan {cls}">📺 {_html.escape(ch)}</span>'


def build(events=None):
    # `events` may be passed in (refresh.py shares one /scores call across pages);
    # otherwise fetch here. Either way it's a single API call.
    if events is None:
        events = fetch_score_events()
    fixtures = fixtures_from_events(events)
    nf = next_fixture(fixtures) if fixtures else None

    if not nf:
        body = ('<div class="card hero"><h2>No upcoming fixture found</h2>'
                '<p>Either the tournament is over or live data is unavailable. '
                'Re-run <code>python next_game.py</code> with an API key set.</p></div>')
        upcoming_rows = ""
    else:
        pred = _prediction(nf["home"], nf["away"])
        pred_html = ""
        if pred:
            score, label, (ph, pd, pa) = pred
            pred_html = f"""
              <div class="pred">
                <span class="pred-label">Model prediction</span>
                <span class="pred-score">{_html.escape(nf['home'])}
                  <b>{score}</b> {_html.escape(nf['away'])}</span>
                <span class="pred-sub">{_html.escape(label)} &middot;
                  {ph*100:.0f}% / {pd*100:.0f}% / {pa*100:.0f}% (W/D/L)</span>
              </div>"""
        host_tag = ""
        body = f"""
          <div class="card hero">
            <span class="eyebrow">NEXT UP</span>
            <h2 class="match">{_html.escape(nf['home'])}
              <span class="vs">v</span> {_html.escape(nf['away'])}</h2>
            <div class="ko" data-ko="{nf['ko_utc'].isoformat()}">
              <span class="ko-time">{_html.escape(fmt_bst(nf['ko_bst']))}</span>
              {_channel_badge(nf['channel'])}
            </div>
            <div id="countdown" class="countdown">—</div>
            {pred_html}
          </div>"""

        # upcoming fixtures list (next ~12 not-yet-completed after the next one)
        pending = [f for f in fixtures if not f["completed"]]
        rows = []
        for f in pending[1:13]:
            rows.append(
                f'<tr><td class="ko-c">{_html.escape(fmt_bst(f["ko_bst"]))}</td>'
                f'<td class="match-c">{_html.escape(f["home"])} v {_html.escape(f["away"])}</td>'
                f'<td>{_channel_badge(f["channel"])}</td></tr>'
            )
        upcoming_rows = "\n".join(rows)

    doc = (_TEMPLATE
           .replace("{{NAV}}", site_chrome.nav("next"))
           .replace("{{BODY}}", body)
           .replace("{{UPCOMING}}", upcoming_rows))
    out = os.path.join(HERE, "next_game.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(doc)
    if nf:
        print(f"Next game: {nf['home']} v {nf['away']} — "
              f"{fmt_bst(nf['ko_bst'])} on {nf['channel']}")
    print(f"Wrote {out}")
    return out


_TEMPLATE = """<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<!-- Auto-reload every 10 min so the page rolls to the next fixture after one ends. -->
<meta http-equiv="refresh" content="600">
<title>Next Game — World Cup 2026</title>
<style>
  * { box-sizing:border-box; }
  body { font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    margin:0; background:#f6f8fb; color:#22303f; }
  header { background:linear-gradient(135deg,#1d3557,#2a9d8f); color:#fff; padding:30px 24px; }
  header h1 { margin:0; font-size:23px; }
  .wrap { max-width:760px; margin:0 auto; padding:26px 24px 60px; }
  .card { background:#fff; border-radius:14px; box-shadow:0 1px 4px rgba(20,40,70,.10);
    padding:26px; margin-bottom:22px; }
  .hero { text-align:center; border-top:5px solid #2a9d8f; }
  .eyebrow { font-size:12px; font-weight:700; letter-spacing:.12em; color:#2a9d8f; }
  .match { font-size:30px; margin:8px 0 14px; color:#1d3557; line-height:1.2; }
  .match .vs { color:#9aa7b6; font-weight:400; font-size:20px; margin:0 6px; }
  .ko { display:flex; gap:12px; justify-content:center; align-items:center; flex-wrap:wrap; }
  .ko-time { font-size:16px; font-weight:600; color:#46566a; }
  .chan { font-size:13px; font-weight:700; border-radius:20px; padding:4px 12px; color:#fff; }
  .ch-bbc { background:#000; } .ch-itv { background:#d81f7a; } .ch-tbc { background:#9aa7b6; }
  .countdown { margin:18px 0 4px; font-size:34px; font-weight:800; color:#1d3557;
    font-variant-numeric:tabular-nums; letter-spacing:.01em; }
  .pred { margin-top:20px; padding-top:18px; border-top:1px solid #eef2f7; }
  .pred-label { display:block; font-size:11px; font-weight:700; text-transform:uppercase;
    letter-spacing:.06em; color:#8595a6; margin-bottom:4px; }
  .pred-score { display:block; font-size:18px; color:#22303f; }
  .pred-score b { color:#2a9d8f; font-size:21px; margin:0 4px; }
  .pred-sub { display:block; font-size:13px; color:#6b7a8d; margin-top:3px; }
  h3.sec { font-size:16px; color:#46566a; margin:8px 0 10px; }
  table { width:100%; border-collapse:collapse; background:#fff; border-radius:12px;
    overflow:hidden; box-shadow:0 1px 4px rgba(20,40,70,.08); }
  th,td { padding:10px 14px; font-size:13.5px; text-align:left; border-bottom:1px solid #eef2f7; }
  th { background:#f0f4f9; color:#46566a; font-size:11px; text-transform:uppercase; letter-spacing:.03em; }
  tr:last-child td { border-bottom:none; }
  .ko-c { color:#6b7a8d; white-space:nowrap; font-size:12.5px; }
  .match-c { font-weight:600; }
  code { background:#eef2f7; padding:1px 5px; border-radius:4px; }
  footer { max-width:760px; margin:0 auto; padding:0 24px 50px; font-size:12px; color:#8595a6; }
</style></head>
<body>
{{NAV}}
<header><h1>⏱️ Next Game</h1></header>
<div class="wrap">
  {{BODY}}
  <h3 class="sec">Coming up next</h3>
  <table>
    <tr><th>Kick-off (BST)</th><th>Match</th><th>Channel</th></tr>
    {{UPCOMING}}
  </table>
</div>
<footer>
  Kick-off times live from The Odds API, converted to BST (UTC+1). Channels per the
  BBC/ITV World Cup 2026 split; "TBC" where not yet confirmed. Always check your TV guide.
</footer>
<script>
  // Live countdown to kickoff.
  (function () {
    var el = document.querySelector('.ko');
    var out = document.getElementById('countdown');
    if (!el || !out) return;
    var ko = new Date(el.getAttribute('data-ko'));
    function tick() {
      var diff = ko - new Date();
      if (diff <= 0) { out.textContent = 'Kicking off! ⚽'; return; }
      var s = Math.floor(diff / 1000);
      var d = Math.floor(s / 86400); s -= d * 86400;
      var h = Math.floor(s / 3600);  s -= h * 3600;
      var m = Math.floor(s / 60);    s -= m * 60;
      var p = function (n) { return (n < 10 ? '0' : '') + n; };
      out.textContent = (d > 0 ? d + 'd ' : '') + p(h) + ':' + p(m) + ':' + p(s);
    }
    tick(); setInterval(tick, 1000);
  })();
</script>
</body></html>"""


if __name__ == "__main__":
    build()
