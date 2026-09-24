"""Unit tests on small hand-made play-by-play so the math is easy to check."""
import pandas as pd
import pytest

from app import roles, stats
from app.report import edge_verdict


def play(**kw):
    base = {
        "game_id": "2026_01_AAA_BBB", "play_id": 1, "season": 2026, "season_type": "REG", "week": 1,
        "posteam": "ATL", "defteam": "GB", "play_type": "pass", "down": 1, "ydstogo": 10,
        "yardline_100": 60, "qtr": 1, "half_seconds_remaining": 900, "wp": 0.5,
        "fixed_drive": 1, "fixed_drive_result": "Punt",
        "qb_dropback": 1, "qb_scramble": 0, "qb_kneel": 0, "qb_spike": 0, "two_point_attempt": 0,
        "pass_attempt": 1, "rush_attempt": 0, "sack": 0, "complete_pass": 1, "interception": 0,
        "yards_gained": 10, "passing_yards": 10, "receiving_yards": 10, "rushing_yards": None,
        "air_yards": 5, "run_location": None, "run_gap": None,
        "passer_player_id": "QB1", "receiver_player_id": "WR1", "rusher_player_id": None,
        "touchdown": 0, "pass_touchdown": 0, "rush_touchdown": 0,
        "third_down_converted": 0, "third_down_failed": 0, "epa": 0.5, "success": 1,
    }
    base.update(kw)
    return base


@pytest.fixture
def plays():
    rows = [
        play(play_id=1, receiver_player_id="WR1", receiving_yards=30, passing_yards=30, yards_gained=30, air_yards=25),
        play(play_id=2, receiver_player_id="SL1", receiving_yards=8, passing_yards=8, air_yards=4),
        play(play_id=3, receiver_player_id="TE1", receiving_yards=12, passing_yards=12, air_yards=8,
             yardline_100=12, pass_touchdown=1, touchdown=1, fixed_drive=2, fixed_drive_result="Touchdown"),
        play(play_id=4, play_type="run", qb_dropback=0, pass_attempt=0, rush_attempt=1, complete_pass=0,
             receiver_player_id=None, rusher_player_id="RB1", rushing_yards=6, passing_yards=None,
             receiving_yards=None, yards_gained=6, run_location="left", run_gap="tackle"),
        play(play_id=5, play_type="run", qb_dropback=0, pass_attempt=0, rush_attempt=1, complete_pass=0,
             receiver_player_id=None, rusher_player_id="RB1", rushing_yards=12, passing_yards=None,
             receiving_yards=None, yards_gained=12, run_location="middle"),
        # a kneel should be ignored entirely
        play(play_id=6, play_type="run", qb_kneel=1, qb_dropback=0, pass_attempt=0, receiver_player_id=None,
             rusher_player_id="QB1", rushing_yards=-1, passing_yards=None, receiving_yards=None),
    ]
    p = stats.prepare_plays(pd.DataFrame(rows), None, None)
    positions = {"WR1": "WR", "WR2": "WR", "SL1": "WR", "TE1": "TE", "RB1": "RB", "QB1": "QB"}
    team_roles = {"ATL": roles.TeamRoles(starters={"X": "WR1", "SLOT": "SL1"})}
    p["rec_role"] = roles.tag_receiver_roles(p, team_roles, positions)
    p["rush_role"] = roles.tag_rusher_roles(p, positions)
    return p


def test_kneels_are_dropped(plays):
    assert len(plays) == 5


def test_unit_metrics(plays):
    m = stats.unit_metrics(plays, games=1)
    assert m["pass_yds_pg"] == 50
    assert m["rush_yds_pg"] == 18
    assert m["pass_rate"] == pytest.approx(60.0)
    assert m["rec_yds_pg_X"] == 30
    assert m["rec_yds_pg_SLOT"] == 8
    assert m["rec_yds_pg_TE"] == 12
    assert m["deep_att_pg"] == 1
    assert m["deep_yds_pg"] == 30
    assert m["rz_trips_pg"] == 1
    assert m["rz_td_pct"] == 100
    assert m["rb_rush_yds_pg"] == 18
    assert m["exp_pass_pg"] == 1
    assert m["exp_run_pg"] == 1


def test_td_breakdown(plays):
    td = stats.td_breakdown(plays)
    assert td == [{"key": "TE", "label": "Tight ends", "td": 1, "share": 100.0}]


def test_run_direction(plays):
    rd = {b["key"]: b for b in stats.run_direction(plays)}
    assert rd["LT"]["carries"] == 1 and rd["LT"]["ypc"] == 6
    assert rd["M"]["carries"] == 1 and rd["M"]["ypc"] == 12
    assert rd["RE"]["carries"] == 0


def test_slot_is_shortest_adot():
    split = roles._split_roles(["A", "B", "C"], {"A": 12.0, "B": 7.5, "C": 14.0})
    assert split == {"SLOT": "B", "X": "A", "Z": "C"}


def test_manual_override_wins():
    tg = pd.DataFrame({"posteam": ["ATL"] * 3, "receiver_player_id": ["A", "B", "C"], "air_yards": [10, 5, 15]})
    positions = {"A": "WR", "B": "WR", "C": "WR"}
    out = roles.assign_team_roles(["ATL"], tg, positions, {"A": 10, "B": 5, "C": 15}, None,
                                  {"ATL": {"SLOT": "A"}})
    assert out["ATL"].starters["SLOT"] == "A"
    assert "A" not in [pid for r, pid in out["ATL"].starters.items() if r != "SLOT"]
    assert out["ATL"].method == "set by you"


def test_edge_verdicts():
    assert edge_verdict(0.9) == "big_edge"
    assert edge_verdict(0.7) == "edge"
    assert edge_verdict(0.5) == "even"
    assert edge_verdict(0.2) == "tough"
