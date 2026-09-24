"""Metric definitions: labels, number formats and which direction is "good".

`off` / `def` say what is better for that unit when ranking 1-32:
  "high"  higher is better (rank 1 = highest)
  "low"   lower is better  (rank 1 = lowest)
  None    a tendency, not good or bad (rank 1 = highest, shown without color)
"""
from __future__ import annotations

HI, LO, N = "high", "low", None


def _m(label, fmt, off, deff, sub=None, def_label=None, def_sub=None):
    return {"label": label, "fmt": fmt, "off": off, "def": deff, "sub": sub,
            "def_label": def_label or label, "def_sub": def_sub if def_sub is not None else sub}


METRICS: dict[str, dict] = {
    # identity
    "pass_rate": _m("Pass rate", "pct", N, N, "Dropbacks as a share of plays"),
    "run_rate": _m("Run rate", "pct", N, N, "Designed runs as a share of plays"),
    "neutral_pass_rate": _m("Pass rate, neutral game state", "pct", N, N,
                            "1st/2nd down, win chance 20-80%"),
    "plays_pg": _m("Plays / game", "n1", N, N),
    "points_pg": _m("Points / game", "n1", HI, LO, def_label="Points allowed / game"),
    "pa_rate": _m("Play action rate", "pct", N, N, "Share of dropbacks", def_label="Play action faced"),
    "screen_rate": _m("Screen rate", "pct", N, N, "Share of dropbacks", def_label="Screens faced"),
    "motion_rate": _m("Pre-snap motion", "pct", N, N, "Share of plays", def_label="Motion faced"),
    "rz_pass_rate": _m("Red zone pass rate", "pct", N, N, "Inside the 20"),
    "pass_att_pg": _m("Pass attempts / game", "n1", N, N),
    "carries_pg": _m("Carries / game", "n1", N, N),

    # production
    "total_yds_pg": _m("Total yards / game", "n1", HI, LO),
    "pass_yds_pg": _m("Pass yards / game", "n1", HI, LO),
    "rush_yds_pg": _m("Rush yards / game", "n1", HI, LO, "All players, incl. scrambles"),
    "ypa": _m("Yards / pass attempt", "n1", HI, LO),
    "ypc": _m("Yards / carry", "n1", HI, LO),
    "comp_pct": _m("Completion %", "pct", HI, LO),
    "epa_pass": _m("EPA / dropback", "epa", HI, LO, "Expected points added per pass play"),
    "epa_rush": _m("EPA / designed run", "epa", HI, LO),
    "success_rate": _m("Success rate", "pct", HI, LO, "Plays with positive EPA"),
    "third_down_pct": _m("3rd down conversion", "pct", HI, LO),
    "exp_pass_pg": _m("20+ yard completions / game", "n1", HI, LO),
    "exp_run_pg": _m("10+ yard runs / game", "n1", HI, LO),
    "pass_td_pg": _m("Pass TDs / game", "n1", HI, LO),
    "rush_td_pg": _m("Rush TDs / game", "n1", HI, LO),

    # run game
    "rb_rush_yds_pg": _m("RB rush yards / game", "n1", HI, LO),
    "rb_ypc": _m("RB yards / carry", "n1", HI, LO),
    "rb_carries_pg": _m("RB carries / game", "n1", N, N),
    "qb_rush_yds_pg": _m("QB rush yards / game", "n1", HI, LO, "Designed runs and scrambles"),
    "qb_ypc": _m("QB yards / carry", "n1", HI, LO),
    "qb_carries_pg": _m("QB carries / game", "n1", N, N),

    # deep
    "deep_att_pg": _m("Deep attempts / game", "n1", N, N, "20+ air yards", def_label="Deep attempts faced / game"),
    "deep_rate": _m("Deep attempt rate", "pct", N, N, "Share of pass attempts"),
    "deep_comp_pct": _m("Deep completion %", "pct", HI, LO),
    "deep_yds_pg": _m("Deep pass yards / game", "n1", HI, LO),
    "deep_ypa": _m("Yards / deep attempt", "n1", HI, LO),
    "deep_td": _m("Deep TDs", "n0", HI, LO, "Season total"),

    # red zone
    "rz_trips_pg": _m("Red zone trips / game", "n1", HI, LO, "Drives reaching the 20",
                      def_label="Red zone trips allowed / game"),
    "rz_td_pct": _m("Red zone TD rate", "pct", HI, LO, "Trips ending in a TD"),
    "rz_tds": _m("Red zone TDs", "n0", HI, LO, "Season total"),

    # protection / pass rush
    "sack_rate": _m("Sack rate", "pct", LO, HI, "Sacks per dropback", def_label="Sack rate"),
    "sacks_pg": _m("Sacks / game", "n1", LO, HI, def_label="Sacks / game"),
    "pressure_rate": _m("Pressure rate allowed", "pct", LO, HI, "Hurries, hits and sacks",
                        def_label="Pressure rate"),
    "int_rate": _m("Interception rate", "pct", LO, HI, "Per pass attempt"),

    # scheme (defense)
    "man_rate": _m("Man coverage", "pct", N, N, "Cover 0, Cover 1, 2-Man"),
    "zone_rate": _m("Zone coverage", "pct", N, N, "Cover 2, 3, 4, 6 and others"),
    "blitz_rate": _m("Blitz rate faced", "pct", N, N, "Dropbacks with 1+ blitzer",
                     def_label="Blitz rate", def_sub="Dropbacks with 1+ blitzer"),
    "avg_rushers": _m("Pass rushers faced", "n1", N, N, "Average per dropback",
                      def_label="Pass rushers", def_sub="Average per dropback"),
    "ypa_vs_man": _m("Yards / attempt vs man", "n1", HI, LO),
    "epa_vs_man": _m("EPA / dropback vs man", "epa", HI, LO),
    "ypa_vs_zone": _m("Yards / attempt vs zone", "n1", HI, LO),
    "epa_vs_zone": _m("EPA / dropback vs zone", "epa", HI, LO),

    # receiving aggregates
    "rec_yds_pg_ALLWR": _m("WR receiving yards / game", "n1", HI, LO),
    "tgt_share_ALLWR": _m("WR target share", "pct", N, N),
}

for _role, _label in [("X", "X receiver"), ("Z", "Z receiver"), ("SLOT", "Slot receiver"),
                      ("WR", "Other WRs"), ("TE", "Tight ends"), ("RB", "RB receiving")]:
    METRICS[f"tgt_pg_{_role}"] = _m(f"{_label} targets / game", "n1", N, N)
    METRICS[f"tgt_share_{_role}"] = _m(f"{_label} target share", "pct", N, N)
    METRICS[f"rec_pg_{_role}"] = _m(f"{_label} catches / game", "n1", HI, LO)
    METRICS[f"rec_yds_pg_{_role}"] = _m(f"{_label} yards / game", "n1", HI, LO)
    METRICS[f"rec_td_{_role}"] = _m(f"{_label} TDs", "n0", HI, LO)
    METRICS[f"ypt_{_role}"] = _m(f"{_label} yards / target", "n1", HI, LO)


for _slot, _name in (("RB1", "RB1"), ("RB2", "RB2"), ("RB3", "RB3"), ("ALLRB", "All RBs")):
    METRICS[f"{_slot}_yds_pg"] = _m(f"{_name} scrimmage yards / game", "n1", HI, LO)
    METRICS[f"{_slot}_rush_yds_pg"] = _m(f"{_name} rush yards / game", "n1", HI, LO)
    METRICS[f"{_slot}_rec_yds_pg"] = _m(f"{_name} receiving yards / game", "n1", HI, LO)
    METRICS[f"{_slot}_td"] = _m(f"{_name} TDs", "n0", HI, LO)
    METRICS[f"{_slot}_carries_pg"] = _m(f"{_name} carries / game", "n1", N, N)
    METRICS[f"{_slot}_tgt_pg"] = _m(f"{_name} targets / game", "n1", N, N)
    METRICS[f"{_slot}_ypc"] = _m(f"{_name} yards / carry", "n1", HI, LO)
    METRICS[f"{_slot}_rush_td"] = _m(f"{_name} rush TDs", "n0", HI, LO)
    METRICS[f"{_slot}_rec_td"] = _m(f"{_name} receiving TDs", "n0", HI, LO)


OFFENSE_SECTIONS = [
    {"id": "identity", "title": "Identity", "desc": "How they like to move the ball.",
     "rows": ["pass_rate", "run_rate", "neutral_pass_rate", "plays_pg", "points_pg",
              "pa_rate", "screen_rate", "motion_rate"]},
    {"id": "production", "title": "Production", "desc": "Yards, efficiency and big plays.",
     "rows": ["total_yds_pg", "pass_yds_pg", "rush_yds_pg", "ypa", "ypc", "comp_pct",
              "epa_pass", "epa_rush", "success_rate", "third_down_pct", "exp_pass_pg", "exp_run_pg"]},
    {"id": "rushing", "title": "Run game", "desc": "Who runs it and how well.",
     "rows": ["rb_rush_yds_pg", "rb_ypc", "rb_carries_pg", "qb_rush_yds_pg", "qb_ypc", "rush_td_pg"]},
    {"id": "deep", "title": "Deep passing", "desc": "Throws that travel 20+ yards in the air.",
     "rows": ["deep_att_pg", "deep_rate", "deep_comp_pct", "deep_yds_pg", "deep_ypa", "deep_td"]},
    {"id": "redzone", "title": "Red zone", "desc": "Drives that reach the opponent's 20.",
     "rows": ["rz_trips_pg", "rz_td_pct", "rz_tds", "rz_pass_rate"]},
    {"id": "protection", "title": "Protection and turnovers", "desc": "How well they keep the QB clean.",
     "rows": ["sack_rate", "sacks_pg", "pressure_rate", "blitz_rate", "int_rate"]},
]

DEFENSE_SECTIONS = [
    {"id": "scheme", "title": "How they defend", "desc": "Coverage and pass rush habits.",
     "rows": ["man_rate", "zone_rate", "blitz_rate", "avg_rushers", "pressure_rate", "sack_rate", "sacks_pg"]},
    {"id": "coverage", "title": "Man vs zone results", "desc": "What offenses do against each coverage family.",
     "rows": ["ypa_vs_man", "epa_vs_man", "ypa_vs_zone", "epa_vs_zone"]},
    {"id": "overall", "title": "Yards and points allowed", "desc": "The big picture.",
     "rows": ["points_pg", "total_yds_pg", "pass_yds_pg", "rush_yds_pg", "ypa", "comp_pct",
              "epa_pass", "epa_rush", "success_rate", "third_down_pct", "int_rate"]},
    {"id": "run", "title": "Run defense", "desc": "Rushing allowed by position.",
     "rows": ["rb_rush_yds_pg", "rb_ypc", "qb_rush_yds_pg", "ypc", "exp_run_pg", "rush_td_pg"]},
    {"id": "deep", "title": "Deep passes", "desc": "Throws of 20+ air yards against them.",
     "rows": ["deep_att_pg", "deep_comp_pct", "deep_yds_pg", "deep_ypa", "deep_td", "exp_pass_pg"]},
    {"id": "redzone", "title": "Red zone", "desc": "Opponent drives that reach the 20.",
     "rows": ["rz_trips_pg", "rz_td_pct", "rz_tds"]},
]

# Offense metric vs the matching defense metric, for the mismatch finder.
EDGE_DEFS = [
    {"key": "X", "label": "X receiver", "metric": "rec_yds_pg_X", "player_role": "X"},
    {"key": "Z", "label": "Z receiver", "metric": "rec_yds_pg_Z", "player_role": "Z"},
    {"key": "SLOT", "label": "Slot receiver", "metric": "rec_yds_pg_SLOT", "player_role": "SLOT"},
    {"key": "TE", "label": "Tight end", "metric": "rec_yds_pg_TE", "player_role": "TE1"},
    {"key": "RB1", "label": "RB1 (lead back)", "metric": "RB1_yds_pg", "player_role": "RB1"},
    {"key": "RB2", "label": "RB2", "metric": "RB2_yds_pg", "player_role": "RB2"},
    {"key": "RB_rec", "label": "RB receiving", "metric": "rec_yds_pg_RB", "player_role": "RB1"},
    {"key": "RB_rush", "label": "RB rushing", "metric": "rb_rush_yds_pg", "player_role": "RB1"},
    {"key": "QB_rush", "label": "QB rushing", "metric": "qb_rush_yds_pg", "player_role": "QB1"},
    {"key": "deep", "label": "Deep passing", "metric": "deep_yds_pg", "player_role": "DEEP"},
    {"key": "explosive", "label": "Big pass plays", "metric": "exp_pass_pg"},
    {"key": "rz", "label": "Red zone TDs", "metric": "rz_td_pct"},
    {"key": "pass_eff", "label": "Passing efficiency", "metric": "epa_pass", "player_role": "QB1"},
    {"key": "run_eff", "label": "Rushing efficiency", "metric": "epa_rush"},
    {"key": "third", "label": "3rd downs", "metric": "third_down_pct"},
    {"key": "protection", "label": "Pass protection vs pass rush", "metric": "sack_rate"},
]


# Columns on the League rankings page, in order. (key, short header, what it measures)
RANKING_COLUMNS = [
    ("ALLRB_rush_yds_pg", "RB rush", "Rushing yards per game by all running backs"),
    ("ALLRB_yds_pg", "RB total", "Rushing + receiving yards per game by all running backs"),
    ("ALLRB_td", "RB TDs", "Rushing + receiving TDs by running backs, season total"),
    ("pass_yds_pg", "QB pass", "Passing yards per game"),
    ("qb_rush_yds_pg", "QB rush", "QB rushing yards per game (designed runs + scrambles)"),
    ("rec_yds_pg_ALLWR", "All WRs", "Receiving yards per game by all wide receivers"),
    ("rec_yds_pg_X", "X", "Receiving yards per game by the X receiver"),
    ("rec_yds_pg_Z", "Z", "Receiving yards per game by the Z receiver"),
    ("rec_yds_pg_SLOT", "Slot", "Receiving yards per game by the slot receiver"),
    ("rec_yds_pg_TE", "TE (Y)", "Receiving yards per game by tight ends"),
    ("rec_yds_pg_RB", "RB rec", "Receiving yards per game by running backs"),
    ("deep_yds_pg", "Deep", "Yards per game on throws of 20+ air yards"),
]
