"""
Lightweight live refresh: rebuild the two pages that change during match days
(bet_tracker.html and next_game.html) from a SINGLE Odds API /scores call.

This is what the GitHub Action runs on a schedule. Fetching once and sharing the
events across both pages keeps us inside the 500-request/month free tier:
one /scores call costs 2 quota, so 6 runs/day ≈ 360/month.

(predictions + accas are a fixed snapshot rebuilt manually via build_site.py.)
"""

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

from fixtures import fetch_score_events, load_api_key
import track_bets
import next_game


def main():
    api_key = load_api_key()
    events = fetch_score_events(api_key) if api_key else []
    if not api_key:
        print("No API key — pages will show pending/TBC.")

    # Both builders accept pre-fetched events so we make just ONE API call.
    track_bets.main(events=events)
    next_game.build(events=events)
    print("Refreshed bet_tracker.html and next_game.html from one /scores call.")


if __name__ == "__main__":
    main()
