"""Turn raw play-by-play into per-team offense and defense profiles.

Every number is computed for all 32 teams so each team can be ranked 1-32.
Offense stats are grouped by the team with the ball (posteam). Defense stats
use exactly the same formulas grouped by the team on defense (defteam), so
"allowed" numbers line up one-to-one with offensive production.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import roles as roles_mod
from . import sources, teams
from .metrics import METRICS

log = logging.getLogger(__name__)

REC_ROLES = ["X", "Z", "SLOT", "WR", "TE", "RB"]
RUN_BUCKETS = [
    ("LE", "Left end"), ("LT", "Left tackle"), ("LG", "Left guard"), ("M", "Middle"),
    ("RG", "Right guard"), ("RT", "Right tackle"), ("RE", "Right end"),
]
SHELLS = [
    ("COVER_0", "Cover 0"), ("COVER_1", "Cover 1"), ("2_MAN", "2-Man"), ("COVER_2", "Cover 2"),
    ("COVER_3", "Cover 3"), ("COVER_4", "Cover 4"), ("COVER_6", "Cover 6"), ("OTHER", "Other"),
]
TD_LABELS = {
    "X": "X receiver", "Z": "Z receiver", "SLOT": "Slot receiver", "WR": "Other WRs",
    "TE": "Tight ends", "RB_rec": "RB receiving", "RB_rush": "RB rushing",
    "QB_rush": "QB rushing", "OTHER": "Other",
}


def clean(x, nd: int = 1):
    """Round and make JSON-safe (NaN and inf become None)."""
    if x is None:
        return None
    try:
        xf = float(x)
    except (TypeError, ValueError):
        return None
    if math.isnan(xf) or math.isinf(xf):
        return None
    return round(xf, nd)


def pct(num, den):
    return 100.0 * num / den if den else None


def div(num, den):
    return num / den if den else None


@dataclass
class SeasonData:
    season: int
    available: bool
    games: dict = field(default_factory=dict)
    records: dict = field(default_factory=dict)
    points_for: dict = field(default_factory=dict)
    points_against: dict = field(default_factory=dict)
    off: dict = field(default_factory=dict)          # team -> {metric: value}
    deff: dict = field(default_factory=dict)
    off_rank: dict = field(default_factory=dict)     # team -> {metric: rank}
    def_rank: dict = field(default_factory=dict)
    td_off: dict = field(default_factory=dict)
    td_def: dict = field(default_factory=dict)
    run_dir_off: dict = field(default_factory=dict)
    run_dir_def: dict = field(default_factory=dict)
    shells: dict = field(default_factory=dict)
    players: pd.DataFrame | None = None              # one row per (team, player)
    team_roles: dict = field(default_factory=dict)   # team -> TeamRoles
    has_coverage: bool = False
    has_ftn: bool = False
    last_week: int | None = None
    adot: dict = field(default_factory=dict)
    targets: pd.DataFrame | None = None              # target plays, reused for next season's aDOT


# ----------------------------------------------------------------------------
# Play preparation
# ----------------------------------------------------------------------------

def prepare_plays(pbp: pd.DataFrame, part: pd.DataFrame | None, ftn: pd.DataFrame | None) -> pd.DataFrame:
    p = pbp[pbp["season_type"] == "REG"]
    p = p[p["play_type"].isin(["pass", "run"])]
    for col in ["qb_kneel", "qb_spike", "two_point_attempt", "qb_dropback", "qb_scramble", "pass_attempt",
                "sack", "complete_pass", "interception", "touchdown", "pass_touchdown", "rush_touchdown",
                "third_down_converted", "third_down_failed", "success"]:
        p[col] = p[col].fillna(0) if col in p else 0
    p = p[(p["qb_kneel"] != 1) & (p["qb_spike"] != 1) & (p["two_point_attempt"] != 1)]
    p = p[p["posteam"].notna() & p["defteam"].notna()].copy()
    p["posteam"] = p["posteam"].map(teams.normalize)
    p["defteam"] = p["defteam"].map(teams.normalize)
    p["play_id"] = p["play_id"].astype("int64")

    p["dropback"] = p["qb_dropback"] == 1
    p["carry"] = p["play_type"] == "run"
    p["designed_run"] = p["carry"] & (p["qb_scramble"] != 1)
    p["att"] = (p["pass_attempt"] == 1) & (p["sack"] != 1)
    p["target"] = p["att"] & p["receiver_player_id"].notna()
    p["comp"] = p["att"] & (p["complete_pass"] == 1)
    p["pass_yds"] = p["passing_yards"].fillna(0).where(p["att"], 0)
    p["rec_yds"] = p["receiving_yards"].fillna(0).where(p["target"], 0)
    p["rush_yds"] = p["rushing_yards"].fillna(0).where(p["carry"], 0)
    p["deep"] = p["att"] & (p["air_yards"] >= 20)
    p["exp_pass"] = p["comp"] & (p["yards_gained"] >= 20)
    p["exp_run"] = p["carry"] & (p["rush_yds"] >= 10)
    p["rz"] = p["yardline_100"] <= 20
    p["pass_td"] = p["att"] & (p["pass_touchdown"] == 1)
    p["rush_td"] = p["carry"] & (p["rush_touchdown"] == 1)
    p["neutral"] = (p["down"].isin([1, 2]) & p["wp"].between(0.2, 0.8) & (p["half_seconds_remaining"] > 120))

    loc = p["run_location"].fillna("")
    gap = p["run_gap"].fillna("")
    gap_code = gap.map({"end": "E", "tackle": "T", "guard": "G"}).fillna("")
    bucket = np.where(loc == "middle", "M", np.where(loc.isin(["left", "right"]) & (gap_code != ""),
                                                     loc.str[:1].str.upper() + gap_code, ""))
    p["run_bucket"] = pd.Series(bucket, index=p.index).where(p["designed_run"], "")

    if part is not None and len(part):
        pr = part.rename(columns={"nflverse_game_id": "game_id"}).copy()
        pr["play_id"] = pr["play_id"].astype("int64")
        pr = pr.drop_duplicates(["game_id", "play_id"])
        p = p.merge(pr, on=["game_id", "play_id"], how="left")
    if ftn is not None and len(ftn):
        fr = ftn.rename(columns={"nflverse_game_id": "game_id", "nflverse_play_id": "play_id"}).copy()
        fr["play_id"] = fr["play_id"].astype("int64")
        fr = fr.drop_duplicates(["game_id", "play_id"])
        p = p.merge(fr, on=["game_id", "play_id"], how="left")
    return p


# ----------------------------------------------------------------------------
# Unit metrics (same formulas for offense and defense)
# ----------------------------------------------------------------------------

def unit_metrics(d: pd.DataFrame, games: int) -> dict:
    g = games or 0
    db = d[d["dropback"]]
    att = d[d["att"]]
    runs = d[d["carry"]]
    drun = d[d["designed_run"]]
    tg = d[d["target"]]
    m: dict = {"games": g}

    m["plays_pg"] = div(len(d), g)
    m["pass_rate"] = pct(len(db), len(db) + len(drun))
    m["run_rate"] = pct(len(drun), len(db) + len(drun))
    neu = d[d["neutral"]]
    m["neutral_pass_rate"] = pct(neu["dropback"].sum(), neu["dropback"].sum() + neu["designed_run"].sum())

    m["pass_yds_pg"] = div(att["pass_yds"].sum(), g)
    m["rush_yds_pg"] = div(runs["rush_yds"].sum(), g)
    m["total_yds_pg"] = div(att["pass_yds"].sum() + runs["rush_yds"].sum(), g)
    m["pass_att_pg"] = div(len(att), g)
    m["carries_pg"] = div(len(runs), g)
    m["comp_pct"] = pct(att["comp"].sum(), len(att))
    m["ypa"] = div(att["pass_yds"].sum(), len(att))
    m["ypc"] = div(runs["rush_yds"].sum(), len(runs))
    m["epa_pass"] = db["epa"].mean() if len(db) else None
    m["epa_rush"] = drun["epa"].mean() if len(drun) else None
    m["success_rate"] = pct(d["success"].sum(), len(d))
    m["exp_pass_pg"] = div(d["exp_pass"].sum(), g)
    m["exp_run_pg"] = div(d["exp_run"].sum(), g)
    m["sack_rate"] = pct(db["sack"].sum(), len(db))
    m["sacks_pg"] = div(db["sack"].sum(), g)
    m["int_rate"] = pct(att["interception"].sum(), len(att))
    m["pass_td_pg"] = div(d["pass_td"].sum(), g)
    m["rush_td_pg"] = div(d["rush_td"].sum(), g)

    third = d[d["down"] == 3]
    conv, fail = third["third_down_converted"].sum(), third["third_down_failed"].sum()
    m["third_down_pct"] = pct(conv, conv + fail)

    deep = att[att["deep"]]
    m["deep_att_pg"] = div(len(deep), g)
    m["deep_rate"] = pct(len(deep), len(att))
    m["deep_comp_pct"] = pct(deep["comp"].sum(), len(deep))
    m["deep_yds_pg"] = div(deep["pass_yds"].sum(), g)
    m["deep_td"] = float(deep["pass_td"].sum())
    m["deep_ypa"] = div(deep["pass_yds"].sum(), len(deep))

    drives = d.groupby(["game_id", "fixed_drive"]).agg(
        closest=("yardline_100", "min"), result=("fixed_drive_result", "first"))
    rz = drives[drives["closest"] <= 20]
    rz_td = int((rz["result"] == "Touchdown").sum())
    m["rz_trips_pg"] = div(len(rz), g)
    m["rz_td_pct"] = pct(rz_td, len(rz))
    m["rz_tds"] = float(rz_td)
    rzp = d[d["rz"]]
    rz_db = rzp["dropback"].sum()
    m["rz_pass_rate"] = pct(rz_db, rz_db + rzp["designed_run"].sum())

    for role in ("QB", "RB"):
        rr = runs[runs["rush_role"] == role]
        k = role.lower()
        m[f"{k}_rush_yds_pg"] = div(rr["rush_yds"].sum(), g)
        m[f"{k}_carries_pg"] = div(len(rr), g)
        m[f"{k}_ypc"] = div(rr["rush_yds"].sum(), len(rr))
        m[f"{k}_rush_td"] = float(rr["rush_td"].sum())

    for role in REC_ROLES:
        x = tg[tg["rec_role"] == role]
        m[f"tgt_pg_{role}"] = div(len(x), g)
        m[f"tgt_share_{role}"] = pct(len(x), len(tg))
        m[f"rec_pg_{role}"] = div(x["comp"].sum(), g)
        m[f"rec_yds_pg_{role}"] = div(x["rec_yds"].sum(), g)
        m[f"rec_td_{role}"] = float(x["pass_td"].sum())
        m[f"ypt_{role}"] = div(x["rec_yds"].sum(), len(x))
    wr_all = tg[tg["rec_role"].isin(["X", "Z", "SLOT", "WR"])]
    m["rec_yds_pg_ALLWR"] = div(wr_all["rec_yds"].sum(), g)
    m["tgt_share_ALLWR"] = pct(len(wr_all), len(tg))

    # FTN charting
    if "is_play_action" in d.columns:
        cdb = db[db["is_play_action"].notna()]
        call = d[d["is_motion"].notna()]
        if len(cdb):
            m["pa_rate"] = pct(cdb["is_play_action"].astype(bool).sum(), len(cdb))
            m["screen_rate"] = pct(cdb["is_screen_pass"].astype(bool).sum(), len(cdb))
            m["blitz_rate"] = pct((cdb["n_blitzers"].fillna(0) > 0).sum(), len(cdb))
            m["avg_rushers"] = cdb["n_pass_rushers"].mean()
        if len(call):
            m["motion_rate"] = pct(call["is_motion"].astype(bool).sum(), len(call))

    # Participation: coverage and pressure
    if "defense_man_zone_type" in d.columns:
        mz = db[db["defense_man_zone_type"].isin(["MAN_COVERAGE", "ZONE_COVERAGE"])]
        if len(mz):
            man = mz[mz["defense_man_zone_type"] == "MAN_COVERAGE"]
            zone = mz[mz["defense_man_zone_type"] == "ZONE_COVERAGE"]
            m["man_rate"] = pct(len(man), len(mz))
            m["zone_rate"] = pct(len(zone), len(mz))
            m["epa_vs_man"] = man["epa"].mean() if len(man) else None
            m["epa_vs_zone"] = zone["epa"].mean() if len(zone) else None
            m["ypa_vs_man"] = div(man["pass_yds"].sum(), man["att"].sum())
            m["ypa_vs_zone"] = div(zone["pass_yds"].sum(), zone["att"].sum())
        pres = db[db["was_pressure"].notna()]
        if len(pres):
            m["pressure_rate"] = pct(pres["was_pressure"].astype(bool).sum(), len(pres))
    return m


def td_breakdown(d: pd.DataFrame) -> list[dict]:
    counts: dict[str, int] = {}
    for role, n in d[d["pass_td"]]["rec_role"].value_counts().items():
        key = "RB_rec" if role == "RB" else role
        counts[key] = counts.get(key, 0) + int(n)
    for role, n in d[d["rush_td"]]["rush_role"].value_counts().items():
        key = {"RB": "RB_rush", "QB": "QB_rush"}.get(role, "OTHER")
        counts[key] = counts.get(key, 0) + int(n)
    total = sum(counts.values())
    rows = [{"key": k, "label": TD_LABELS.get(k, k), "td": v, "share": clean(pct(v, total))}
            for k, v in counts.items() if v > 0]
    rows.sort(key=lambda r: -r["td"])
    return rows


def run_direction(d: pd.DataFrame) -> list[dict]:
    runs = d[d["designed_run"] & (d["run_bucket"] != "")]
    out = []
    for code, label in RUN_BUCKETS:
        x = runs[runs["run_bucket"] == code]
        out.append({"key": code, "label": label, "carries": int(len(x)),
                    "ypc": clean(div(x["rush_yds"].sum(), len(x))),
                    "share": clean(pct(len(x), len(runs)))})
    return out


def coverage_shells(d: pd.DataFrame) -> list[dict] | None:
    if "defense_coverage_type" not in d.columns:
        return None
    db = d[d["dropback"] & d["defense_coverage_type"].notna()]
    if not len(db):
        return None
    known = {k for k, _ in SHELLS if k != "OTHER"}
    types = db["defense_coverage_type"].where(db["defense_coverage_type"].isin(known), "OTHER")
    counts = types.value_counts()
    return [{"key": k, "label": label, "pct": clean(pct(int(counts.get(k, 0)), len(db)))} for k, label in SHELLS]


def player_table(p: pd.DataFrame, positions: dict, names: dict) -> pd.DataFrame:
    """Per (team, player) receiving, rushing and passing totals."""
    tg = p[p["target"]]
    rec = tg.groupby(["posteam", "receiver_player_id"]).agg(
        targets=("target", "size"), rec=("comp", "sum"), rec_yds=("rec_yds", "sum"),
        rec_td=("pass_td", "sum"), air=("air_yards", "mean"), deep_tgts=("deep", "sum"),
        rz_tgts=("rz", "sum"), role=("rec_role", "first"), games_rec=("game_id", "nunique"),
    ).reset_index().rename(columns={"posteam": "team", "receiver_player_id": "player_id"})

    ru = p[p["carry"] & p["rusher_player_id"].notna()]
    rush = ru.groupby(["posteam", "rusher_player_id"]).agg(
        carries=("carry", "size"), rush_yds=("rush_yds", "sum"), rush_td=("rush_td", "sum"),
        rz_carries=("rz", "sum"), games_rush=("game_id", "nunique"),
    ).reset_index().rename(columns={"posteam": "team", "rusher_player_id": "player_id"})

    pa = p[p["att"] & p["passer_player_id"].notna()]
    passing = pa.groupby(["posteam", "passer_player_id"]).agg(
        pass_att=("att", "size"), pass_cmp=("comp", "sum"), pass_yds=("pass_yds", "sum"),
        pass_td=("pass_td", "sum"), ints=("interception", "sum"), games_pass=("game_id", "nunique"),
    ).reset_index().rename(columns={"posteam": "team", "passer_player_id": "player_id"})

    df = rec.merge(rush, on=["team", "player_id"], how="outer").merge(passing, on=["team", "player_id"], how="outer")
    num_cols = [c for c in df.columns if c not in ("team", "player_id", "role", "air")]
    df[num_cols] = df[num_cols].fillna(0)
    df["games"] = df[["games_rec", "games_rush", "games_pass"]].max(axis=1)
    df["name"] = df["player_id"].map(names)
    df["position"] = df["player_id"].map(positions)
    team_tgts = df.groupby("team")["targets"].transform("sum")
    df["tgt_share"] = np.where(team_tgts > 0, 100 * df["targets"] / team_tgts, 0)
    df["total_td"] = df["rec_td"] + df["rush_td"]
    return df


# ----------------------------------------------------------------------------
# Ranks
# ----------------------------------------------------------------------------

def rank_all(values: dict[str, dict], side: str) -> dict[str, dict]:
    """Rank every metric 1-32 where 1 is best for that unit (or highest when neutral)."""
    frame = pd.DataFrame(values).T
    ranks: dict[str, dict] = {t: {} for t in frame.index}
    for key, meta in METRICS.items():
        if key not in frame.columns:
            continue
        better = meta.get("off") if side == "off" else meta.get("def")
        col = pd.to_numeric(frame[key], errors="coerce")
        if col.notna().sum() == 0:
            continue
        ascending = better == "low"
        r = col.rank(ascending=ascending, method="min")
        for t, v in r.items():
            if not pd.isna(v):
                ranks[t][key] = int(v)
    return ranks


# ----------------------------------------------------------------------------
# Season build
# ----------------------------------------------------------------------------

def team_records(sched: pd.DataFrame, season: int):
    s = sched[(sched["season"] == season) & (sched["game_type"] == "REG")].dropna(subset=["home_score", "away_score"])
    rec: dict[str, list[int]] = {}
    pf: dict[str, float] = {}
    pa: dict[str, float] = {}
    for _, g in s.iterrows():
        h, a = teams.normalize(g["home_team"]), teams.normalize(g["away_team"])
        hs, as_ = float(g["home_score"]), float(g["away_score"])
        for t, us, them in ((h, hs, as_), (a, as_, hs)):
            w, l_, tie = rec.setdefault(t, [0, 0, 0])
            rec[t] = [w + (us > them), l_ + (us < them), tie + (us == them)]
            pf[t] = pf.get(t, 0) + us
            pa[t] = pa.get(t, 0) + them
    records = {t: (f"{w}-{l_}" + (f"-{tie}" if tie else "")) for t, (w, l_, tie) in rec.items()}
    return records, pf, pa


def latest_depth(depth: pd.DataFrame | None) -> pd.DataFrame | None:
    if depth is None or not len(depth):
        return None
    d = depth.copy()
    d["team"] = d["team"].map(teams.normalize)
    last = d.groupby("team")["dt"].transform("max")
    return d[d["dt"] == last]


def build_season(season: int, current: bool, prior_targets: pd.DataFrame | None = None) -> SeasonData:
    raw = sources.pbp(season)
    if raw is None or not len(raw) or not (raw["season_type"] == "REG").any():
        return SeasonData(season=season, available=False)

    plist = sources.players()
    positions = dict(zip(plist["gsis_id"], plist["position"]))
    names = dict(zip(plist["gsis_id"], plist["display_name"]))
    part = sources.participation(season)
    ftn = sources.ftn(season)

    p = prepare_plays(raw, part, ftn)
    tg = p[p["target"]]

    adot = roles_mod.adot_table(tg, prior_targets) if current else roles_mod.adot_table(tg)
    all_teams = sorted(set(p["posteam"]) | set(p["defteam"]))
    depth_latest = latest_depth(sources.depth_charts(season)) if current else None
    overrides = roles_mod.load_overrides(season)
    team_roles = roles_mod.assign_team_roles(all_teams, tg, positions, adot, depth_latest, overrides)

    p["rec_role"] = roles_mod.tag_receiver_roles(p, team_roles, positions)
    p["rush_role"] = roles_mod.tag_rusher_roles(p, positions)

    sched = sources.schedule()
    records, pf, pa = team_records(sched, season)

    sd = SeasonData(season=season, available=True, team_roles=team_roles, records=records,
                    points_for=pf, points_against=pa, adot=adot,
                    has_coverage=bool(part is not None and len(part)),
                    has_ftn=bool(ftn is not None and len(ftn)),
                    last_week=int(p["week"].max()))

    games = p.groupby("posteam")["game_id"].nunique().to_dict()
    for t in all_teams:
        n = int(games.get(t, 0))
        sd.games[t] = n
        off = p[p["posteam"] == t]
        de = p[p["defteam"] == t]
        sd.off[t] = unit_metrics(off, n)
        sd.deff[t] = unit_metrics(de, n)
        sd.off[t]["points_pg"] = div(pf.get(t, 0), n)
        sd.deff[t]["points_pg"] = div(pa.get(t, 0), n)
        sd.td_off[t] = td_breakdown(off)
        sd.td_def[t] = td_breakdown(de)
        sd.run_dir_off[t] = run_direction(off)
        sd.run_dir_def[t] = run_direction(de)
        sd.shells[t] = coverage_shells(de)

    sd.off_rank = rank_all(sd.off, "off")
    sd.def_rank = rank_all(sd.deff, "def")
    sd.players = player_table(p, positions, names)
    sd.targets = tg[["receiver_player_id", "air_yards"]]
    return sd
