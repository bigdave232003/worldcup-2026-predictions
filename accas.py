"""
Build accumulator suggestions from live Sky Bet odds, in escalating tiers from
"sensible" to "shoot the moon", and render them as an HTML section.

Returns are REAL (computed from live Sky Bet decimal odds). Two "chance to land"
figures are shown per acca:
  - Bookie %  : 1 / combined-odds  — the market's view (the realistic one).
  - Model %   : product of our model probabilities — our view (optimistic for
                favourites, since the model is top-heavy; shown for comparison).
"""

import functools
import html
import operator

STAKE = 10.0   # £ stake used for the headline return figures


def _pct(x):
    """Format a probability percentage, keeping tiny values legible."""
    if x >= 1:
        return f"{x:.1f}%"
    if x >= 0.001:
        return f"{x:.3f}%"
    return f"~1 in {round(100/x):,}" if x > 0 else "0%"


def _combine(legs):
    odds = functools.reduce(operator.mul, [l["sky_odds"] for l in legs], 1.0)
    model_p = functools.reduce(operator.mul, [l["model_prob"] for l in legs], 1.0)
    return odds, model_p


def _favourite_per_match(bets, one_per_team=False):
    """Shortest-priced (most likely) Sky Bet selection per match, sorted
    short->long. If one_per_team, keep only a team's strongest single leg so a
    banker doesn't hinge twice on the same side."""
    by_match = {}
    for b in bets:
        m = b["match"]
        if m not in by_match or b["sky_odds"] < by_match[m]["sky_odds"]:
            by_match[m] = b
    legs = sorted(by_match.values(), key=lambda x: x["sky_odds"])
    if not one_per_team:
        return legs
    seen, out = set(), []
    for l in legs:
        team = l["pick"].replace(" win", "")
        if team not in seen:
            seen.add(team); out.append(l)
    return out


def _build_to_target(bets, target, max_legs):
    """Assemble up to `max_legs` legs whose COMBINED odds reach ~`target`.

    To hit a big target with few legs we must use longer-priced picks, so we
    work out the per-leg odds needed (target ** (1/max_legs)) and, for each new
    leg, choose the eligible pick whose odds are closest to that running need.
    This naturally uses short favourites for low targets and punchier picks for
    high ones, while keeping every leg a selection the model believes in.

    Eligible = positive-EV, model rates >=33%. One leg per match and per team."""
    by_match = {}
    for b in bets:
        m = b["match"]
        if b["ev"] <= 0 or b["model_prob"] < 0.33:
            continue
        # keep the highest-EV eligible pick within each match
        if m not in by_match or b["ev"] > by_match[m]["ev"]:
            by_match[m] = b
    pool = list(by_match.values())

    legs, seen_teams, seen_matches, odds = [], set(), set(), 1.0
    while len(legs) < max_legs and odds < target:
        remaining_legs = max_legs - len(legs)
        need_total = target / odds
        per_leg_need = need_total ** (1.0 / remaining_legs)   # ideal next-leg odds
        # pick the unused eligible leg with odds closest to the per-leg need
        cands = [b for b in pool
                 if b["match"] not in seen_matches
                 and b["pick"].replace(" win", "") not in seen_teams]
        if not cands:
            break
        b = min(cands, key=lambda x: abs(x["sky_odds"] - per_leg_need))
        legs.append(b); odds *= b["sky_odds"]
        seen_matches.add(b["match"]); seen_teams.add(b["pick"].replace(" win", ""))
    return sorted(legs, key=lambda x: x["sky_odds"]), odds


def build_target_accas(bets):
    """Accas aimed at ~10x, 20x, 100x returns from live odds."""
    specs = [
        (10, 5, "✨", "Tenfold", "Aiming for ~10&times; your stake from five "
                                "value picks the model rates above the market."),
        (20, 6, "💎", "Twenty-Up", "Aiming for ~20&times; from six longer-priced "
                                   "value legs — genuinely tough but not absurd."),
        (100, 7, "🌠", "The Ton", "Aiming for ~100&times; from seven underdogs the "
                                  "model rates higher than the market. A real long shot."),
    ]
    tiers = []
    for target, max_legs, emoji, name, blurb in specs:
        legs, odds = _build_to_target(bets, target, max_legs)
        model_p = functools.reduce(operator.mul, [l["model_prob"] for l in legs], 1.0)
        tiers.append(dict(
            name=name, emoji=emoji, blurb=blurb, legs=legs,
            combined_odds=odds, model_pct=model_p * 100,
            bookie_pct=(1.0 / odds) * 100 if odds else 0.0,
            returns=odds * STAKE, target=target,
        ))
    return tiers


def build_accas(bets):
    """Return a list of tier dicts built from the live odds pool `bets`
    (each: match, pick, model_prob, sky_odds, ev)."""
    # One leg per team so an acca never hinges twice on the same side.
    favs = _favourite_per_match(bets, one_per_team=True)

    # Value longshots for the wild tier: positive-EV picks at juicy prices.
    longshots = sorted(
        [b for b in bets if b["ev"] > 0 and b["sky_odds"] >= 2.0],
        key=lambda x: x["ev"], reverse=True,
    )
    # de-dupe longshots by match, keep order
    seen, ls = set(), []
    for b in longshots:
        if b["match"] not in seen:
            seen.add(b["match"]); ls.append(b)

    tiers = [
        dict(name="The Banker", emoji="🛡️", blurb=(
            "Four shortest-priced favourites where Sky Bet and the model agree. "
            "Most likely to land — but small return."),
            legs=favs[:4]),
        dict(name="The Sensible Six", emoji="✅", blurb=(
            "Six strong favourites. Still favourite-heavy, a bit more upside."),
            legs=favs[:6]),
        dict(name="The Ambitious", emoji="🎯", blurb=(
            "Eight legs — favourites plus a couple of the model's value picks. "
            "Landing this would be a good day."),
            legs=favs[:8]),
        dict(name="Shoot the Moon", emoji="🚀", blurb=(
            "Twelve of the model's biggest value longshots stacked together. "
            "Tiny chance, life-changing-if-it-hits return. Pure fantasy."),
            legs=(ls[:12] if len(ls) >= 12 else favs[:12])),
    ]

    for t in tiers:
        odds, model_p = _combine(t["legs"])
        t["combined_odds"] = odds
        t["model_pct"] = model_p * 100
        t["bookie_pct"] = (1.0 / odds) * 100 if odds else 0.0
        t["returns"] = odds * STAKE
    return tiers


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------
def _card(t):
    legrows = "\n".join(
        f'<tr><td class="team">{html.escape(l["pick"])}</td>'
        f'<td class="venue">{html.escape(l["match"])}</td>'
        f'<td class="score">{l["sky_odds"]:.2f}</td></tr>'
        for l in t["legs"]
    )
    ret = t["returns"]
    ret_str = f"£{ret:,.0f}" if ret >= 1000 else f"£{ret:,.2f}"
    return f"""
        <div class="acca">
          <div class="acca-head">
            <h3>{t['emoji']} {html.escape(t['name'])}
              <span class="legcount">{len(t['legs'])} legs</span></h3>
            <p class="blurb">{t['blurb']}</p>
          </div>
          <table class="acca-legs">
            <tr><th>Selection</th><th>Match</th><th class="score">Sky</th></tr>
            {legrows}
          </table>
          <div class="acca-foot">
            <div class="stat"><span class="lbl">Combined odds</span>
              <span class="val">{t['combined_odds']:,.2f}</span></div>
            <div class="stat hi"><span class="lbl">£{STAKE:.0f} returns</span>
              <span class="val">{ret_str}</span></div>
            <div class="stat"><span class="lbl">Chance (bookie)</span>
              <span class="val">{_pct(t['bookie_pct'])}</span></div>
            <div class="stat"><span class="lbl">Chance (model)</span>
              <span class="val">{_pct(t['model_pct'])}</span></div>
          </div>
        </div>"""


def render_html(tiers, target_tiers=None):
    section = [f"""<h2>🎰 Accumulator Ideas
        <span class="grpteams">live Sky Bet odds &middot; £{STAKE:.0f} stake</span></h2>
      <p class="acca-note">Returns are real (live Sky Bet decimal odds). "Chance (bookie)"
      is the market's implied probability — the realistic one. "Chance (model)" is our
      model's view. Every acca is &minus;EV once the bookmaker margin compounds:
      for entertainment only, never a sure thing.</p>"""]

    section.append('<h3 class="acca-sub">Risk tiers — sensible to silly</h3>')
    section.append(f'<div class="acca-grid">{"".join(_card(t) for t in tiers)}</div>')

    if target_tiers:
        section.append('<h3 class="acca-sub">Target returns — pick your multiplier</h3>')
        section.append(f'<div class="acca-grid">'
                       f'{"".join(_card(t) for t in target_tiers)}</div>')
    return "\n".join(section)
