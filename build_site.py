"""
Rebuild the whole static site in one command:

    python build_site.py

Produces three pages that link to each other via the shared nav bar:
  - index.html                  landing page
  - worldcup_predictions.html   match predictions + simulation + acca ideas
  - bet_tracker.html            live tracker for the placed accumulators

Run this locally whenever you want to refresh the predictions snapshot or the
bet results, then commit & push. (The GitHub Action refreshes only the tracker
on a schedule.)
"""

import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

import site_chrome
import predict_worldcup
import track_bets

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    print("=" * 60)
    print("Building World Cup 2026 site")
    print("=" * 60)

    # 1. Landing page (static, no data dependency)
    index_path = os.path.join(HERE, "index.html")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(site_chrome.render_index())
    print(f"✓ index.html")

    # 2. Predictions page (model + 20k simulation + live-odds accas)
    print("\nBuilding predictions page (this runs the simulation)...")
    predict_worldcup.run()

    # 3. Bet tracker page (fetches live results if an API key is present)
    print("\nBuilding bet tracker page...")
    track_bets.main()

    print("\n" + "=" * 60)
    print("Site built. Pages:")
    for name in ("index.html", "worldcup_predictions.html", "bet_tracker.html"):
        print(f"  {os.path.join(HERE, name)}")
    print("Open index.html to browse.")


if __name__ == "__main__":
    main()
