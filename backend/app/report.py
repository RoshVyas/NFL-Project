"""Assemble everything the dashboard shows for one matchup."""
from __future__ import annotations

import logging
import math
import threading
from datetime import date, datetime, timedelta

import pandas as pd

from . import config, sources, teams
from . import roles as roles_mod
from .metrics import DEFENSE_SECTIONS, EDGE_DEFS, METRICS, OFFENSE_SECTIONS, RANKING_COLUMNS
from .stats import RB_SLOTS, REC_ROLES, SeasonData, build_season, clean, latest_depth

log = logging.getLogger(__name__)

_cache: dict[int, tuple[tuple, SeasonData]] = {}
_depth_cache: dict[int, tuple[float, pd.DataFrame | None]] = {}
_build_lock = threading.Lock()


# ----------------------------------------------------------------------------
# Season cache
# ----------------------------------------------------------------------------

def _fingerprint(season: int) -> tuple:
    return sources.file_versions(season) + (roles_mod.overrides_version(), date.today().isoformat())


def get_season(season: int) -> SeasonData:
    prior_season, cur_season = config.seasons()
    with _build_lock:
        # Touch the sources first so stale files are refreshed before we compare fingerprints.
        sources.refresh_if_stale(season)
        fp = _fingerprint(season)
        hit = _cache.get(season)
        if hit and hit[0] == fp:
            return hit[1]
    prior_targets = None
    if season == cur_season:
        prior_targets = get_season(prior_season).targets
    with _build_lock:
        log.info("Building %s season profiles", season)
        sd = build_season(season, current=(season == cur_season), prior_targets=prior_targets)
        _cache[season] = (_fingerprint(season), sd)
        return sd


def get_depth(season: int) -> pd.DataFrame | None:
    df = sources.depth_charts(season)
    if df is None:
        return None
    key = sources.file_versions(season)[3]
    hit = _depth_cache.get(season)
    if hit and hit[0] == key:
        return hit[1]
    latest = latest_depth(df)
    _depth_cache[season] = (key, latest)
    return latest


def clear_cache() -> None:
    _cache.clear()
    _depth_cache.clear()


# ----------------------------------------------------------------------------
# Schedule
# ----------------------------------------------------------------------------

def _game_row(g) -> dict:
    away, home = teams.normalize(g["away_team"]), teams.normalize(g["home_team"])

    def num(x):
        return None if pd.isna(x) else float(x)

    return {
        "game_id": g["game_id"],
        "season": int(g["season"]),
        "week": int(g["week"]),
        "game_type": g["game_type"],
        "gameday": g["gameday"],
        "weekday": g["weekday"],
        "gametime": g["gametime"],
        "away": away,
        "home": home,
        "away_team": teams.info(away),
        "home_team": teams.info(home),
        "stadium": None if pd.isna(g.get("stadium")) else g.get("stadium"),
        "location": g.get("location"),
        "spread_line": num(g.get("spread_line")),
        "total_line": num(g.get("total_line")),
        "away_score": num(g.get("away_score")),
        "home_score": num(g.get("home_score")),
        "away_qb": None if pd.isna(g.get("away_qb_name")) else g.get("away_qb_name"),
        "home_qb": None if pd.isna(g.get("home_qb_name")) else g.get("home_qb_name"),
    }


def upcoming_games(days: int = 7, today: date | None = None) -> list[dict]:
    today = today or date.today()
    s = sources.schedule()
    s = s[s["gameday"].notna()].copy()
    s["_d"] = pd.to_datetime(s["gameday"]).dt.date
    window = s[(s["_d"] >= today) & (s["_d"] <= today + timedelta(days=days))]
    if window.empty:
        window = s[s["_d"] >= today].sort_values(["_d", "gametime"]).head(16)
    window = window.sort_values(["_d", "gametime"])
    return [json_safe(_game_row(g)) for _, g in window.iterrows()]


def find_game(game_id: str) -> dict | None:
    s = sources.schedule()
    row = s[s["game_id"] == game_id]
    return _game_row(row.iloc[0]) if len(row) else None


# ----------------------------------------------------------------------------
# Players
# ----------------------------------------------------------------------------

def _num(x, nd=1):
    return clean(x, nd)


def _player_row(r, games: int | None = None) -> dict:
    g = games or r.get("games") or 0
    return {
        "id": r["player_id"],
        "name": r["name"] if isinstance(r.get("name"), str) else r["player_id"],
        "pos": r.get("position"),
        "role": r.get("role") if isinstance(r.get("role"), str) else None,
        "games": int(r.get("games") or 0),
        "targets": int(r.get("targets") or 0),
        "tgt_share": _num(r.get("tgt_share")),
        "rec": int(r.get("rec") or 0),
        "rec_yds": int(r.get("rec_yds") or 0),
        "rec_td": int(r.get("rec_td") or 0),
        "adot": _num(r.get("air")),
        "deep_tgts": int(r.get("deep_tgts") or 0),
        "rz_tgts": int(r.get("rz_tgts") or 0),
        "carries": int(r.get("carries") or 0),
        "rush_yds": int(r.get("rush_yds") or 0),
        "rush_td": int(r.get("rush_td") or 0),
        "rz_carries": int(r.get("rz_carries") or 0),
        "pass_att": int(r.get("pass_att") or 0),
        "pass_cmp": int(r.get("pass_cmp") or 0),
        "pass_yds": int(r.get("pass_yds") or 0),
        "pass_td": int(r.get("pass_td") or 0),
        "ints": int(r.get("ints") or 0),
        "total_td": int(r.get("total_td") or 0),
        "rec_yds_pg": _num((r.get("rec_yds") or 0) / g) if g else None,
        "rush_yds_pg": _num((r.get("rush_yds") or 0) / g) if g else None,
    }


def _team_players(sd: SeasonData, team: str) -> pd.DataFrame:
    if not sd.available or sd.players is None:
        return pd.DataFrame()
    return sd.players[sd.players["team"] == team]


def player_season_line(sd: SeasonData, pid: str) -> dict | None:
    """A player's totals for a season across every team he played for."""
    if not sd.available or sd.players is None or not pid:
        return None
    rows = sd.players[sd.players["player_id"] == pid]
    if rows.empty:
        return None
    teams_played = rows["team"].tolist()
    agg = rows.drop(columns=["team", "player_id", "name", "position", "role", "air"]).sum(numeric_only=True)
    r = agg.to_dict()
    r.update({"player_id": pid, "name": rows["name"].iloc[0], "position": rows["position"].iloc[0],
              "role": rows["role"].iloc[0]})
    total_air = (rows["air"].fillna(0) * rows["targets"]).sum()
    r["air"] = total_air / r["targets"] if r.get("targets") else None
    r["games"] = rows["games"].sum()
    line = _player_row(r)
    line["teams"] = teams_played
    if len(teams_played) > 1:
        line["tgt_share"] = None
    return line


# ----------------------------------------------------------------------------
# Depth chart
# ----------------------------------------------------------------------------

def depth_chart(depth: pd.DataFrame | None, team: str, team_roles: roles_mod.TeamRoles | None) -> dict:
    if depth is None:
        return {"updated": None, "groups": []}
    d = depth[depth["team"] == team]
    if d.empty:
        return {"updated": None, "groups": []}
    role_by_id = {pid: r for r, pid in (team_roles.starters.items() if team_roles else [])}
    deep = team_roles.deep_threat if team_roles else None

    groups = []
    order = {"3WR 1TE": 0, "Base 4-3 D": 1, "Base 3-4 D": 1, "Special Teams": 2}
    for grp, gd in sorted(d.groupby("pos_grp"), key=lambda kv: order.get(kv[0], 3)):
        title = "Offense" if order.get(grp) == 0 else "Defense" if order.get(grp) == 1 else grp
        positions = []
        wr_i = 0
        for (slot, abb), pd_ in sorted(gd.groupby(["pos_slot", "pos_abb"]), key=lambda kv: kv[0][0]):
            pd_ = pd_.sort_values("pos_rank")
            label = abb
            if abb == "WR":
                wr_i += 1
                label = f"WR{wr_i}"
            positions.append({
                "pos": label,
                "pos_name": pd_["pos_name"].iloc[0],
                "players": [{
                    "id": row.gsis_id if isinstance(row.gsis_id, str) else None,
                    "name": row.player_name,
                    "depth": i + 1,
                    "role": role_by_id.get(row.gsis_id),
                    "deep_threat": bool(deep and row.gsis_id == deep),
                } for i, row in enumerate(pd_.itertuples())],
            })
        if title == "Offense":
            positions.sort(key=lambda p: _OFF_ORDER.get(p["pos"][:2] if p["pos"].startswith("WR") else p["pos"], 99))
        groups.append({"title": title, "formation": grp, "positions": positions})
    return {"updated": d["dt"].iloc[0], "groups": groups}


_OFF_ORDER = {"QB": 0, "RB": 1, "FB": 2, "WR": 3, "TE": 4, "LT": 5, "LG": 6, "C": 7, "RG": 8, "RT": 9}


def lineup_ids(depth: pd.DataFrame | None, team: str) -> dict[str, list[str]]:
    """Starters in depth order by position for the offense."""
    out: dict[str, list[str]] = {}
    if depth is None:
        return out
    d = depth[(depth["team"] == team) & (depth["pos_grp"] == "3WR 1TE")].sort_values("pos_rank")
    for abb in ("QB", "RB", "TE", "WR", "FB"):
        out[abb] = [p for p in dict.fromkeys(d[d["pos_abb"] == abb]["gsis_id"].tolist()) if isinstance(p, str)]
    return out


def resolve_player(role: str, sd_cur: SeasonData, team: str, lineup: dict) -> str | None:
    tr = sd_cur.team_roles.get(team) if sd_cur.available else None
    if role in ("X", "Z", "SLOT"):
        return tr.starters.get(role) if tr else None
    if role == "DEEP":
        return tr.deep_threat if tr else None
    if role in ("RB1", "RB2") and sd_cur.available:
        leaders = _rb_leaders(sd_cur, team)
        picks = [ids[0] for ids in (leaders["RB1"], leaders["RB2"]) if ids]
        idx = int(role[-1]) - 1
        if len(picks) > idx:
            return picks[idx]
    pos, idx = role[:-1], int(role[-1]) - 1
    ids = lineup.get(pos, [])
    return ids[idx] if len(ids) > idx else None


def _name(pid, sds: list[SeasonData], depth: pd.DataFrame | None) -> str | None:
    if not pid:
        return None
    for sd in sds:
        if sd.available and sd.players is not None:
            m = sd.players[sd.players["player_id"] == pid]
            if len(m):
                return m["name"].iloc[0]
    if depth is not None:
        m = depth[depth["gsis_id"] == pid]
        if len(m):
            return m["player_name"].iloc[0]
    return pid


# ----------------------------------------------------------------------------
# Team sections
# ----------------------------------------------------------------------------

def _section_rows(section: dict, side: str, team: str, sds: list[SeasonData]) -> dict:
    rows = []
    for key in section["rows"]:
        meta = METRICS[key]
        values = {}
        for sd in sds:
            if not sd.available:
                continue
            src = sd.off if side == "off" else sd.deff
            ranks = sd.off_rank if side == "off" else sd.def_rank
            v = src.get(team, {}).get(key)
            nd = 2 if meta["fmt"] == "epa" else (0 if meta["fmt"] == "n0" else 1)
            values[str(sd.season)] = {"v": clean(v, nd), "rank": ranks.get(team, {}).get(key)}
        rows.append({
            "key": key,
            "label": meta["label"] if side == "off" else meta["def_label"],
            "sub": meta["sub"] if side == "off" else meta["def_sub"],
            "fmt": meta["fmt"],
            "better": meta[side],
            "values": values,
        })
    return {"id": section["id"], "title": section["title"], "desc": section["desc"], "rows": rows}


def _role_table(side: str, team: str, sds: list[SeasonData]) -> list[dict]:
    out = []
    for role in REC_ROLES:
        row = {"role": role, "label": roles_mod.ROLE_LABELS[role], "values": {}, "players": {}}
        for sd in sds:
            if not sd.available:
                continue
            src = sd.off if side == "off" else sd.deff
            ranks = sd.off_rank if side == "off" else sd.def_rank
            m = src.get(team, {})
            row["values"][str(sd.season)] = {
                "tgt_pg": clean(m.get(f"tgt_pg_{role}")),
                "tgt_share": clean(m.get(f"tgt_share_{role}")),
                "rec_pg": clean(m.get(f"rec_pg_{role}")),
                "yds_pg": clean(m.get(f"rec_yds_pg_{role}")),
                "td": clean(m.get(f"rec_td_{role}"), 0),
                "ypt": clean(m.get(f"ypt_{role}")),
                "rank": ranks.get(team, {}).get(f"rec_yds_pg_{role}"),
                "td_rank": ranks.get(team, {}).get(f"rec_td_{role}"),
            }
            if side == "off":
                tp = _team_players(sd, team)
                tp = tp[tp["role"] == role].sort_values("targets", ascending=False)
                row["players"][str(sd.season)] = [
                    {"id": r.player_id, "name": r.name, "targets": int(r.targets), "yds": int(r.rec_yds),
                     "td": int(r.rec_td)} for r in tp.head(3).itertuples()]
        out.append(row)
    return out


def _rb_leaders(sd: SeasonData, team: str) -> dict[str, list[str]]:
    """Players who most often filled each RB slot for a team, e.g. {"RB1": [id, ...]}."""
    tp = _team_players(sd, team)
    out = {}
    taken: set[str] = set()
    for slot in RB_SLOTS:
        col = f"games_{slot}"
        if tp.empty or col not in tp:
            out[slot] = []
            continue
        cand = tp[(tp[col] > 0) & ~tp["player_id"].isin(taken)]
        cand = cand.assign(_touch=cand["carries"] + cand["targets"]).sort_values([col, "_touch"], ascending=False)
        ids = cand["player_id"].tolist()
        out[slot] = ids
        if ids:
            taken.add(ids[0])
    return out


def _rb_table(side: str, team: str, sds: list[SeasonData]) -> list[dict]:
    out = []
    for slot in RB_SLOTS + ["ALLRB"]:
        label = {"RB1": "RB1", "RB2": "RB2", "RB3": "RB3+", "ALLRB": "All RBs"}[slot]
        row = {"slot": slot, "label": label, "values": {}, "players": {}}
        for sd in sds:
            if not sd.available:
                continue
            src = sd.off if side == "off" else sd.deff
            ranks = sd.off_rank if side == "off" else sd.def_rank
            m, r = src.get(team, {}), ranks.get(team, {})
            row["values"][str(sd.season)] = {
                "carries_pg": clean(m.get(f"{slot}_carries_pg")),
                "rush_yds_pg": clean(m.get(f"{slot}_rush_yds_pg")),
                "ypc": clean(m.get(f"{slot}_ypc")),
                "tgt_pg": clean(m.get(f"{slot}_tgt_pg")),
                "rec_yds_pg": clean(m.get(f"{slot}_rec_yds_pg")),
                "yds_pg": clean(m.get(f"{slot}_yds_pg")),
                "rank": r.get(f"{slot}_yds_pg"),
                "rush_td": clean(m.get(f"{slot}_rush_td"), 0),
                "rec_td": clean(m.get(f"{slot}_rec_td"), 0),
                "td": clean(m.get(f"{slot}_td"), 0),
                "td_rank": r.get(f"{slot}_td"),
            }
            if side == "off" and slot != "ALLRB":
                names = dict(zip(sd.players["player_id"], sd.players["name"]))
                tp = _team_players(sd, team).set_index("player_id")
                row["players"][str(sd.season)] = [
                    {"id": pid, "name": names.get(pid, pid), "games": int(tp.loc[pid, f"games_{slot}"])}
                    for pid in _rb_leaders(sd, team)[slot][:2]]
        out.append(row)
    return out


def _tendencies_def(sd: SeasonData, team: str) -> list[dict]:
    if not sd.available:
        return []
    m, r = sd.deff.get(team, {}), sd.def_rank.get(team, {})
    out = []
    if m.get("man_rate") is not None:
        man = m["man_rate"]
        if man >= 38:
            out.append({"text": f"Man-heavy ({man:.0f}% man)", "tone": "info"})
        elif man <= 25:
            out.append({"text": f"Zone-heavy ({100 - man:.0f}% zone)", "tone": "info"})
        else:
            out.append({"text": f"Mixes man and zone ({man:.0f}% man)", "tone": "info"})
    shells = sd.shells.get(team)
    if shells:
        top = max((s for s in shells if s["key"] != "OTHER"), key=lambda s: s["pct"] or 0)
        out.append({"text": f"Favourite coverage: {top['label']} ({top['pct']:.0f}%)", "tone": "info"})
    if m.get("blitz_rate") is not None and r.get("blitz_rate"):
        br, rk = m["blitz_rate"], r["blitz_rate"]
        if rk <= 8:
            out.append({"text": f"Blitzes a lot ({br:.0f}%, #{rk} in NFL)", "tone": "info"})
        elif rk >= 25:
            out.append({"text": f"Rarely blitzes ({br:.0f}%)", "tone": "info"})
        else:
            out.append({"text": f"Average blitz rate ({br:.0f}%)", "tone": "info"})
    for key, good, bad in [
        ("pressure_rate", "Gets lots of pressure", "Struggles to get pressure"),
        ("rb_rush_yds_pg", "Stingy vs RB runs", "Leaky vs RB runs"),
        ("deep_yds_pg", "Limits deep shots", "Gets beaten deep"),
        ("rec_yds_pg_TE", "Shuts down TEs", "Struggles vs TEs"),
        ("rec_yds_pg_SLOT", "Tough on slot WRs", "Soft vs slot WRs"),
        ("rz_td_pct", "Stout in the red zone", "Gives up red zone TDs"),
    ]:
        rk = r.get(key)
        if rk and rk <= 6:
            out.append({"text": good, "tone": "good"})
        elif rk and rk >= 27:
            out.append({"text": bad, "tone": "bad"})
    return out


def _tendencies_off(sd: SeasonData, team: str) -> list[dict]:
    if not sd.available:
        return []
    m, r = sd.off.get(team, {}), sd.off_rank.get(team, {})
    out = []
    if m.get("neutral_pass_rate") is not None:
        npr, rk = m["neutral_pass_rate"], r.get("neutral_pass_rate")
        if rk and rk <= 8:
            out.append({"text": f"Pass-first ({npr:.0f}% in neutral situations)", "tone": "info"})
        elif rk and rk >= 25:
            out.append({"text": f"Run-first ({100 - npr:.0f}% runs in neutral situations)", "tone": "info"})
        else:
            out.append({"text": f"Balanced ({npr:.0f}% pass in neutral situations)", "tone": "info"})
    if r.get("pa_rate") and r["pa_rate"] <= 8:
        out.append({"text": f"Lots of play action ({m['pa_rate']:.0f}%)", "tone": "info"})
    if r.get("deep_rate") and r["deep_rate"] <= 8:
        out.append({"text": "Takes a lot of deep shots", "tone": "info"})
    best = max(("X", "Z", "SLOT", "TE", "RB"), key=lambda k: m.get(f"rec_yds_pg_{k}") or 0)
    out.append({"text": f"Most productive receiver spot: {roles_mod.ROLE_LABELS[best]}", "tone": "info"})
    for key, good, bad in [
        ("epa_pass", "Efficient passing game", "Inefficient passing game"),
        ("epa_rush", "Efficient run game", "Inefficient run game"),
        ("rz_td_pct", "Finishes in the red zone", "Stalls in the red zone"),
        ("sack_rate", "Keeps the QB clean", "Gives up lots of sacks"),
    ]:
        rk = r.get(key)
        if rk and rk <= 6:
            out.append({"text": good, "tone": "good"})
        elif rk and rk >= 27:
            out.append({"text": bad, "tone": "bad"})
    return out


def _key_players(team: str, sds: list[SeasonData], lineup: dict, sd_cur: SeasonData, depth) -> list[dict]:
    slots = [("QB1", "Quarterback"), ("RB1", "RB1"), ("RB2", "RB2"),
             ("X", "X receiver"), ("Z", "Z receiver"), ("SLOT", "Slot receiver"),
             ("TE1", "TE1"), ("TE2", "TE2")]
    out = []
    for key, label in slots:
        pid = resolve_player(key, sd_cur, team, lineup)
        if not pid:
            continue
        tr = sd_cur.team_roles.get(team) if sd_cur.available else None
        out.append({
            "slot": key,
            "label": label,
            "id": pid,
            "name": _name(pid, sds, depth),
            "deep_threat": bool(tr and tr.deep_threat == pid),
            "seasons": {str(sd.season): player_season_line(sd, pid) for sd in sds if sd.available},
        })
    return out


def _leaders(sd: SeasonData, team: str) -> dict:
    tp = _team_players(sd, team)
    if tp.empty:
        return {"targets": [], "td": [], "rushers": [], "passers": [], "rz": [], "deep": []}
    g = sd.games.get(team) or None

    def rows(df):
        return [_player_row(r, g) for r in df.to_dict("records")]

    return {
        "targets": rows(tp[tp["targets"] > 0].sort_values(["targets", "rec_yds"], ascending=False).head(10)),
        "td": rows(tp[tp["total_td"] > 0].sort_values(["total_td", "rec_yds"], ascending=False).head(8)),
        "rushers": rows(tp[tp["carries"] > 0].sort_values("carries", ascending=False).head(5)),
        "passers": rows(tp[tp["pass_att"] > 0].sort_values("pass_att", ascending=False).head(2)),
        "rz": rows(tp[(tp["rz_tgts"] + tp["rz_carries"]) > 0]
                   .assign(_rz=lambda x: x["rz_tgts"] + x["rz_carries"])
                   .sort_values("_rz", ascending=False).head(6).drop(columns="_rz")),
        "deep": rows(tp[tp["deep_tgts"] > 0].sort_values("deep_tgts", ascending=False).head(5)),
    }


def _role_info(sd: SeasonData, team: str) -> dict | None:
    if not sd.available:
        return None
    tr = sd.team_roles.get(team)
    if not tr:
        return None
    names = dict(zip(sd.players["player_id"], sd.players["name"])) if sd.players is not None else {}
    tp = _team_players(sd, team)
    wr_options = tp[tp["position"] == "WR"].sort_values("targets", ascending=False)
    return {
        "method": tr.method,
        "starters": {r: {"id": pid, "name": names.get(pid, pid), "adot": sd.adot.get(pid)}
                     for r, pid in tr.starters.items()},
        "deep_threat": {"id": tr.deep_threat, "name": names.get(tr.deep_threat)} if tr.deep_threat else None,
        "options": [{"id": r.player_id, "name": r.name, "targets": int(r.targets), "adot": clean(r.air)}
                    for r in wr_options.itertuples()],
    }


def team_report(team: str, sds: list[SeasonData], depth: pd.DataFrame | None) -> dict:
    sd_cur = sds[-1]
    lineup = lineup_ids(depth, team)
    by_season = {str(sd.season): sd for sd in sds}
    return {
        "team": teams.info(team),
        "records": {s: sd.records.get(team) for s, sd in by_season.items() if sd.available},
        "games": {s: sd.games.get(team, 0) for s, sd in by_season.items() if sd.available},
        "offense": {
            "sections": [_section_rows(s, "off", team, sds) for s in OFFENSE_SECTIONS],
            "roles": _role_table("off", team, sds),
            "rb_depth": _rb_table("off", team, sds),
            "td": {s: sd.td_off.get(team, []) for s, sd in by_season.items() if sd.available},
            "run_dir": {s: sd.run_dir_off.get(team, []) for s, sd in by_season.items() if sd.available},
            "leaders": {s: _leaders(sd, team) for s, sd in by_season.items() if sd.available},
            "tendencies": {s: _tendencies_off(sd, team) for s, sd in by_season.items() if sd.available},
            "key_players": _key_players(team, sds, lineup, sd_cur, depth),
        },
        "defense": {
            "sections": [_section_rows(s, "def", team, sds) for s in DEFENSE_SECTIONS],
            "roles": _role_table("def", team, sds),
            "rb_depth": _rb_table("def", team, sds),
            "td": {s: sd.td_def.get(team, []) for s, sd in by_season.items() if sd.available},
            "run_dir": {s: sd.run_dir_def.get(team, []) for s, sd in by_season.items() if sd.available},
            "shells": {s: sd.shells.get(team) for s, sd in by_season.items() if sd.available},
            "tendencies": {s: _tendencies_def(sd, team) for s, sd in by_season.items() if sd.available},
        },
        "depth_chart": depth_chart(depth, team, sd_cur.team_roles.get(team) if sd_cur.available else None),
        "role_info": {s: _role_info(sd, team) for s, sd in by_season.items() if sd.available},
    }


# ----------------------------------------------------------------------------
# Mismatches
# ----------------------------------------------------------------------------

def edge_verdict(score: float | None) -> str | None:
    if score is None:
        return None
    if score >= 0.78:
        return "big_edge"
    if score >= 0.64:
        return "edge"
    if score <= 0.36:
        return "tough"
    return "even"


def edges(off_team: str, def_team: str, sds: list[SeasonData], depth: pd.DataFrame | None) -> list[dict]:
    """Rank offense strengths against defense weaknesses.

    For each area: offense strength = how high the offense ranks (1 = best),
    defense weakness = how low the defense ranks (32 = gives up the most).
    Score 0-1: 1 means the NFL's best offense in that area against its worst defense.
    """
    sd_cur = sds[-1]
    lineup = lineup_ids(depth, off_team)
    out = []
    for e in EDGE_DEFS:
        seasons = {}
        scores = []
        for sd in sds:
            if not sd.available or not sd.games.get(off_team) or not sd.games.get(def_team):
                continue
            n = len(sd.off_rank)
            o_rank = sd.off_rank.get(off_team, {}).get(e["metric"])
            d_rank = sd.def_rank.get(def_team, {}).get(e["metric"])
            if o_rank is None or d_rank is None:
                continue
            score = ((n - o_rank + 1) / n + d_rank / n) / 2
            meta = METRICS[e["metric"]]
            nd = 2 if meta["fmt"] == "epa" else 1
            seasons[str(sd.season)] = {
                "off_value": clean(sd.off[off_team].get(e["metric"]), nd),
                "off_rank": o_rank,
                "def_value": clean(sd.deff[def_team].get(e["metric"]), nd),
                "def_rank": d_rank,
                "score": round(score, 3),
                "verdict": edge_verdict(score),
            }
            scores.append(score)
        if not seasons:
            continue
        pid = resolve_player(e["player_role"], sd_cur, off_team, lineup) if e.get("player_role") else None
        out.append({
            "key": e["key"],
            "label": e["label"],
            "metric": e["metric"],
            "metric_label": METRICS[e["metric"]]["label"],
            "fmt": METRICS[e["metric"]]["fmt"],
            "player": {"id": pid, "name": _name(pid, sds, depth)} if pid else None,
            "seasons": seasons,
            "score": round(sum(scores) / len(scores), 3),
            "verdict": edge_verdict(sum(scores) / len(scores)),
        })
    out.sort(key=lambda x: -x["score"])
    return out


# ----------------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------------

def league_rankings(season: int, side: str) -> dict:
    """Every team's value and 1-32 rank for the League rankings page."""
    sd = get_season(season)
    if not sd.available:
        return {"season": season, "side": side, "available": False, "columns": [], "teams": []}
    src = sd.off if side == "off" else sd.deff
    ranks = sd.off_rank if side == "off" else sd.def_rank
    columns = [{"key": k, "label": label, "desc": desc, "fmt": METRICS[k]["fmt"],
                "better": METRICS[k][side]} for k, label, desc in RANKING_COLUMNS]
    rows = []
    for team in sorted(src):
        rows.append({
            "team": teams.info(team),
            "games": sd.games.get(team, 0),
            "record": sd.records.get(team),
            "values": {c["key"]: {"v": clean(src[team].get(c["key"]), 0 if c["fmt"] == "n0" else 1),
                                  "rank": ranks.get(team, {}).get(c["key"])} for c in columns},
        })
    return json_safe({"season": season, "side": side, "available": True, "last_week": sd.last_week,
                      "columns": columns, "teams": rows})


def json_safe(obj):
    """Replace NaN/inf (which JSON can't encode) with None, recursively."""
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, dict):
        return {k: json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_safe(v) for v in obj]
    if hasattr(obj, "item") and not isinstance(obj, (str, bytes)):  # numpy scalars
        return json_safe(obj.item())
    return obj


def matchup(away: str, home: str, game: dict | None = None) -> dict:
    away, home = teams.normalize(away), teams.normalize(home)
    prior, cur = config.seasons()
    sds = [get_season(prior), get_season(cur)]
    depth = get_depth(cur)
    if depth is None or depth[depth["team"].isin([away, home])].empty:
        depth = get_depth(prior)
    return json_safe({
        "game": game,
        "seasons": [sd.season for sd in sds if sd.available],
        "season_notes": {
            str(sd.season): {
                "available": sd.available,
                "last_week": sd.last_week,
                "has_coverage": sd.has_coverage,
                "has_ftn": sd.has_ftn,
            } for sd in sds
        },
        "away": team_report(away, sds, depth),
        "home": team_report(home, sds, depth),
        "edges": {
            "away_offense": edges(away, home, sds, depth),
            "home_offense": edges(home, away, sds, depth),
        },
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    })
