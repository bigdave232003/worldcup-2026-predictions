# ⚽ World Cup 2026 — Predictions & Bets

A home-grown Poisson–Elo model for the 2026 FIFA World Cup (USA · Mexico · Canada):
every group-stage match predicted, the whole bracket simulated, and my own
accumulators tracked live.

**Live site:** https://bigdave232003.github.io/worldcup-2026-predictions/

## Pages
- **Predictions** — score, win/draw/loss probability and a most-likely result for all
  72 group-stage matches, a 20,000-run Monte Carlo tournament simulation, and
  accumulator ideas priced from live Sky Bet odds.
- **My Bets** — live tracker for three placed accumulators (Tenfold, Twenty-Up, The Ton),
  auto-updating with real match results.

## How it works
Team strength = world-football Elo blended with bookmaker odds, adjusted for recent form,
injuries and host-nation advantage. Goals are modelled with a Poisson process; the
tournament is simulated 20,000 times. Knockout slotting uses FIFA's official Annex C
table (all 495 third-place combinations). Odds and results come from
[The Odds API](https://the-odds-api.com).

## Rebuild locally
```bash
# Optional: provide an Odds API key to fetch live odds/results
echo "ODDS_API_KEY=your_key" > .env

python build_site.py     # rebuilds all three pages
```
Individual steps: `python predict_worldcup.py` (predictions + sim + accas),
`python track_bets.py` (refresh bet results only).

## Auto-updating
A scheduled GitHub Action (`.github/workflows/update-tracker.yml`) re-runs the bet
tracker daily using an `ODDS_API_KEY` repository secret and commits any changes.

---
*For entertainment only — model estimates, not betting advice. Every accumulator is
−EV once the bookmaker margin compounds.*
