"""
World Cup 2026 prediction data — snapshot as of 10 June 2026.

All figures gathered via web research the day before kickoff:
  - Elo ratings   : eloratings.net (live feed), 47/48 teams directly sourced
  - FIFA rank     : FIFA / Wikipedia (1 April 2026 release, last before the cut)
  - Title odds    : bettingodds.com + BetMGM (decimal), 10 June 2026
  - Form / injuries / host notes: ESPN, Wikipedia, news (early June 2026)

Elo is the primary strength signal (most complete + most predictive). Form,
injuries and host advantage are applied as Elo-equivalent adjustments in
model.py, where all the tunable weights live.
"""

# ---------------------------------------------------------------------------
# TEAM STRENGTH
#   elo      : World Football Elo (eloratings.net), 10 Jun 2026
#   fifa     : FIFA world ranking position (approx below 20)
#   odds     : bookmaker decimal odds to win the tournament (None if unpriced)
#   form     : recent-form rating in Elo-equivalent points (see model.FORM_*)
#              positive = hot, negative = cold. 0 = no clear signal / unknown.
#   inj      : injury/absence penalty in Elo points (0 = no notable absences)
# ---------------------------------------------------------------------------
TEAMS = {
    # team                  elo   fifa  odds    form  inj
    "Spain":              dict(elo=2157, fifa=2,  odds=5.0,   form=12, inj=0),
    "Argentina":          dict(elo=2114, fifa=3,  odds=11.0,  form=25, inj=0),
    "France":             dict(elo=2063, fifa=1,  odds=6.0,   form=15, inj=0),
    "England":            dict(elo=2021, fifa=4,  odds=9.0,   form=0,  inj=0),
    "Brazil":             dict(elo=1991, fifa=6,  odds=11.0,  form=15, inj=0),
    "Portugal":           dict(elo=1986, fifa=5,  odds=9.5,   form=15, inj=0),
    "Colombia":           dict(elo=1982, fifa=13, odds=55.0,  form=5,  inj=0),
    "Netherlands":        dict(elo=1948, fifa=7,  odds=22.0,  form=0,  inj=0),
    "Ecuador":            dict(elo=1938, fifa=24, odds=110.0, form=0,  inj=0),
    "Germany":            dict(elo=1932, fifa=10, odds=17.0,  form=18, inj=0),
    "Norway":             dict(elo=1914, fifa=30, odds=38.0,  form=0,  inj=0),
    "Croatia":            dict(elo=1912, fifa=11, odds=140.0, form=-5, inj=0),
    "Türkiye":            dict(elo=1911, fifa=26, odds=100.0, form=0,  inj=0),
    "Japan":              dict(elo=1906, fifa=18, odds=65.0,  form=12, inj=0),
    "Belgium":            dict(elo=1894, fifa=9,  odds=46.0,  form=8,  inj=0),
    "Uruguay":            dict(elo=1892, fifa=17, odds=95.0,  form=0,  inj=0),
    "Switzerland":        dict(elo=1891, fifa=19, odds=85.0,  form=0,  inj=0),
    "Mexico":             dict(elo=1875, fifa=15, odds=70.0,  form=25, inj=0),
    "Senegal":            dict(elo=1860, fifa=14, odds=151.0, form=0,  inj=0),
    "Paraguay":           dict(elo=1834, fifa=40, odds=580.0, form=0,  inj=0),
    "Austria":            dict(elo=1830, fifa=22, odds=220.0, form=0,  inj=0),
    "Morocco":            dict(elo=1827, fifa=8,  odds=55.0,  form=8,  inj=0),
    "Panama":             dict(elo=1730, fifa=37, odds=None,  form=0,  inj=0),
    "Canada":             dict(elo=1788, fifa=28, odds=390.0, form=10, inj=0),
    "Scotland":           dict(elo=1782, fifa=36, odds=None,  form=0,  inj=0),
    "Australia":          dict(elo=1777, fifa=26, odds=None,  form=0,  inj=0),
    "Iran":               dict(elo=1772, fifa=20, odds=None,  form=0,  inj=0),
    "Algeria":            dict(elo=1760, fifa=36, odds=None,  form=0,  inj=0),
    "South Korea":        dict(elo=1758, fifa=23, odds=None,  form=0,  inj=0),
    "Czech Republic":     dict(elo=1740, fifa=42, odds=None,  form=0,  inj=0),
    "United States":      dict(elo=1726, fifa=16, odds=67.0,  form=-15,inj=0),
    "Uzbekistan":         dict(elo=1714, fifa=57, odds=None,  form=0,  inj=0),
    "Sweden":             dict(elo=1712, fifa=43, odds=270.0, form=0,  inj=0),
    "Egypt":              dict(elo=1696, fifa=33, odds=None,  form=0,  inj=0),
    "Ivory Coast":        dict(elo=1695, fifa=41, odds=None,  form=0,  inj=0),
    "Jordan":             dict(elo=1680, fifa=62, odds=None,  form=0,  inj=0),
    "Ghana":              dict(elo=1620, fifa=73, odds=None,  form=0,  inj=0),
    "DR Congo":           dict(elo=1652, fifa=56, odds=None,  form=0,  inj=0),
    "Tunisia":            dict(elo=1628, fifa=45, odds=None,  form=0,  inj=0),
    "Iraq":               dict(elo=1618, fifa=58, odds=None,  form=0,  inj=0),
    "Bosnia and Herzegovina": dict(elo=1595, fifa=76, odds=None, form=0, inj=0),
    "Cape Verde":         dict(elo=1578, fifa=70, odds=None,  form=0,  inj=0),
    "Saudi Arabia":       dict(elo=1576, fifa=60, odds=None,  form=0,  inj=0),
    "New Zealand":        dict(elo=1562, fifa=85, odds=None,  form=0,  inj=0),
    "Haiti":              dict(elo=1548, fifa=83, odds=None,  form=0,  inj=0),
    "South Africa":       dict(elo=1517, fifa=58, odds=None,  form=0,  inj=0),
    "Curaçao":            dict(elo=1434, fifa=82, odds=None,  form=0,  inj=0),
    "Qatar":              dict(elo=1421, fifa=52, odds=None,  form=0,  inj=0),
}

# ---------------------------------------------------------------------------
# GROUPS  — each ordered [t1, t2, t3, t4] so the standard round-robin below
# reproduces the real Matchday-1 pairings (t1 v t2, t3 v t4).
# ---------------------------------------------------------------------------
GROUPS = {
    "A": ["Mexico", "South Africa", "South Korea", "Czech Republic"],
    "B": ["Canada", "Bosnia and Herzegovina", "Qatar", "Switzerland"],
    "C": ["Brazil", "Morocco", "Haiti", "Scotland"],
    "D": ["United States", "Paraguay", "Australia", "Türkiye"],
    "E": ["Germany", "Curaçao", "Ivory Coast", "Ecuador"],
    "F": ["Netherlands", "Japan", "Sweden", "Tunisia"],
    "G": ["Belgium", "Egypt", "Iran", "New Zealand"],
    "H": ["Spain", "Cape Verde", "Saudi Arabia", "Uruguay"],
    "I": ["France", "Senegal", "Iraq", "Norway"],
    "J": ["Argentina", "Algeria", "Austria", "Jordan"],
    "K": ["Portugal", "DR Congo", "Uzbekistan", "Colombia"],
    "L": ["England", "Croatia", "Ghana", "Panama"],
}

# Host nations (partisan crowd + familiar conditions => Elo boost in model.py)
HOSTS = {"United States", "Mexico", "Canada"}

# ---------------------------------------------------------------------------
# MATCHDAY-1 FIXTURES — exact dates & venues (high confidence, Fox Sports).
# Keyed by frozenset of the two teams so the schedule generator can attach
# real dates/venues to the round-robin pairings it produces.
# ---------------------------------------------------------------------------
MD1_FIXTURES = {
    frozenset(["Mexico", "South Africa"]):              ("Thu 11 Jun", "Estadio Azteca, Mexico City"),
    frozenset(["South Korea", "Czech Republic"]):       ("Thu 11 Jun", "Guadalajara"),
    frozenset(["Canada", "Bosnia and Herzegovina"]):    ("Fri 12 Jun", "BMO Field, Toronto"),
    frozenset(["United States", "Paraguay"]):           ("Fri 12 Jun", "SoFi Stadium, Los Angeles"),
    frozenset(["Qatar", "Switzerland"]):                ("Sat 13 Jun", "San Francisco Bay Area"),
    frozenset(["Brazil", "Morocco"]):                   ("Sat 13 Jun", "MetLife, New York/NJ"),
    frozenset(["Haiti", "Scotland"]):                   ("Sat 13 Jun", "Gillette, Boston"),
    frozenset(["Australia", "Türkiye"]):                ("Sat 13 Jun", "BC Place, Vancouver"),
    frozenset(["Germany", "Curaçao"]):                  ("Sun 14 Jun", "NRG Stadium, Houston"),
    frozenset(["Netherlands", "Japan"]):                ("Sun 14 Jun", "AT&T Stadium, Dallas"),
    frozenset(["Ivory Coast", "Ecuador"]):              ("Sun 14 Jun", "Philadelphia"),
    frozenset(["Sweden", "Tunisia"]):                   ("Sun 14 Jun", "Monterrey"),
    frozenset(["Spain", "Cape Verde"]):                 ("Mon 15 Jun", "Mercedes-Benz, Atlanta"),
    frozenset(["Belgium", "Egypt"]):                    ("Mon 15 Jun", "Seattle"),
    frozenset(["Saudi Arabia", "Uruguay"]):             ("Mon 15 Jun", "Miami"),
    frozenset(["Iran", "New Zealand"]):                 ("Mon 15 Jun", "SoFi Stadium, Los Angeles"),
    frozenset(["France", "Senegal"]):                   ("Tue 16 Jun", "MetLife, New York/NJ"),
    frozenset(["Iraq", "Norway"]):                      ("Tue 16 Jun", "Gillette, Boston"),
    frozenset(["Argentina", "Algeria"]):                ("Tue 16 Jun", "Kansas City"),
    frozenset(["Austria", "Jordan"]):                   ("Tue 16 Jun", "San Francisco Bay Area"),
    frozenset(["Portugal", "DR Congo"]):                ("Wed 17 Jun", "NRG Stadium, Houston"),
    frozenset(["England", "Croatia"]):                  ("Wed 17 Jun", "AT&T Stadium, Dallas"),
    frozenset(["Ghana", "Panama"]):                     ("Wed 17 Jun", "BMO Field, Toronto"),
    frozenset(["Uzbekistan", "Colombia"]):              ("Wed 17 Jun", "Estadio Azteca, Mexico City"),
}

# Round-robin template over the ordered group list [0,1,2,3].
# Covers all six pairings; MD1 matches the real fixtures above.
ROUND_ROBIN = {
    1: [(0, 1), (2, 3)],   # Matchday 1 — real dates/venues attached
    2: [(0, 2), (3, 1)],   # Matchday 2 — 18–23 Jun (window)
    3: [(0, 3), (1, 2)],   # Matchday 3 — 24–27 Jun (window, simultaneous)
}

MATCHDAY_WINDOW = {1: "11–17 Jun", 2: "18–23 Jun", 3: "24–27 Jun"}
