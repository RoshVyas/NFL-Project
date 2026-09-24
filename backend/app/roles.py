"""Work out each team's X, Z and slot receiver.

No free data source records where a receiver lines up on every snap, so roles
are assigned per team and season with a simple, explainable rule:

1. Pick the three starting wide receivers.
   - Current season: the top three WRs on the latest ESPN depth chart.
   - Past seasons: the three WRs with the most targets for that team.
2. The starter with the shortest average depth of target (aDOT) is the slot.
   Slot receivers mostly run shorter, inside routes. This is a best guess:
   it is usually right but not always, which is why roles can be edited.
3. Of the other two, the higher one on the depth chart (or in targets) is X,
   the other is Z.
4. Any role you set in the app (saved per season) wins over the rule above.

Every other WR is grouped as "Other WR". TEs, RBs and FBs keep their position.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

import pandas as pd

from . import config

WR_ROLES = ("X", "Z", "SLOT")
ROLE_LABELS = {
    "X": "X receiver",
    "Z": "Z receiver",
    "SLOT": "Slot receiver",
    "WR": "Other WRs",
    "TE": "Tight ends",
    "RB": "RB receiving",
    "QB": "Quarterback",
    "OTHER": "Other",
}
MIN_ADOT_TARGETS = 8
DEEP_THREAT_ADOT = 12.0


def position_group(pos: str | None) -> str:
    pos = (pos or "").upper()
    if pos == "WR":
        return "WR"
    if pos == "TE":
        return "TE"
    if pos in ("RB", "FB", "HB"):
        return "RB"
    if pos == "QB":
        return "QB"
    return "OTHER"


@dataclass
class TeamRoles:
    starters: dict[str, str] = field(default_factory=dict)  # role -> gsis_id
    method: str = ""
    deep_threat: str | None = None

    def role_of(self, gsis_id: str) -> str | None:
        for role, pid in self.starters.items():
            if pid == gsis_id:
                return role
        return None


def load_overrides(season: int | None = None) -> dict:
    """Manual role picks saved from the app, as {season: {team: {role: gsis_id}}}."""
    try:
        data = json.loads(config.ROLE_OVERRIDES_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}
    if season is None:
        return data
    return data.get(str(season), {})


def save_override(season: int, team: str, roles: dict[str, str | None]) -> dict:
    data = load_overrides()
    by_team = data.setdefault(str(season), {})
    clean = {r: pid for r, pid in roles.items() if r in WR_ROLES and pid}
    if clean:
        by_team[team] = clean
    else:
        by_team.pop(team, None)
    config.USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.ROLE_OVERRIDES_FILE.write_text(json.dumps(data, indent=2, sort_keys=True))
    return data


def overrides_version() -> float:
    p = config.ROLE_OVERRIDES_FILE
    return p.stat().st_mtime if p.exists() else 0.0


def adot_table(*target_frames: pd.DataFrame) -> dict[str, float]:
    """Average depth of target per player across the given seasons of target plays."""
    frames = [f[["receiver_player_id", "air_yards"]] for f in target_frames if f is not None and len(f)]
    if not frames:
        return {}
    t = pd.concat(frames).dropna()
    g = t.groupby("receiver_player_id")["air_yards"].agg(["mean", "count"])
    g = g[g["count"] >= MIN_ADOT_TARGETS]
    return g["mean"].round(1).to_dict()


def _split_roles(candidates: list[str], adot: dict[str, float]) -> dict[str, str]:
    candidates = [c for c in dict.fromkeys(candidates) if c]
    roles: dict[str, str] = {}
    if not candidates:
        return roles
    slot = None
    if len(candidates) >= 3:
        known = [c for c in candidates[:3] if c in adot]
        slot = min(known, key=lambda c: adot[c]) if known else candidates[2]
        roles["SLOT"] = slot
    outside = [c for c in candidates[:3] if c != slot]
    if outside:
        roles["X"] = outside[0]
    if len(outside) > 1:
        roles["Z"] = outside[1]
    return roles


def depth_wr_order(depth_latest: pd.DataFrame, team: str) -> list[str]:
    if depth_latest is None or not len(depth_latest):
        return []
    d = depth_latest[(depth_latest["team"] == team) & (depth_latest["pos_abb"] == "WR")]
    d = d.dropna(subset=["gsis_id"]).sort_values(["pos_rank", "pos_slot"])
    return list(dict.fromkeys(d["gsis_id"].tolist()))


def target_wr_order(targets: pd.DataFrame, team: str, positions: dict[str, str]) -> list[str]:
    t = targets[targets["posteam"] == team]
    counts = t["receiver_player_id"].value_counts()
    return [pid for pid in counts.index if position_group(positions.get(pid)) == "WR"]


def assign_team_roles(
    teams: list[str],
    targets: pd.DataFrame,
    positions: dict[str, str],
    adot: dict[str, float],
    depth_latest: pd.DataFrame | None,
    overrides: dict | None,
) -> dict[str, TeamRoles]:
    """Return X/Z/SLOT starters for every team in one season."""
    out: dict[str, TeamRoles] = {}
    for team in teams:
        order = depth_wr_order(depth_latest, team) if depth_latest is not None else []
        method = "depth chart + aDOT"
        if len(order) < 3:
            order = target_wr_order(targets, team, positions)
            method = "targets + aDOT"
        tr = TeamRoles(starters=_split_roles(order, adot), method=method)

        manual = (overrides or {}).get(team)
        if manual:
            # A manually placed player leaves any role the rule gave them.
            for role, pid in manual.items():
                for r, existing in list(tr.starters.items()):
                    if existing == pid and r != role:
                        del tr.starters[r]
                tr.starters[role] = pid
            tr.method = "set by you"

        wrs = [pid for pid in tr.starters.values() if adot.get(pid) is not None]
        if wrs:
            deepest = max(wrs, key=lambda p: adot[p])
            if adot[deepest] >= DEEP_THREAT_ADOT:
                tr.deep_threat = deepest
        out[team] = tr
    return out


def tag_receiver_roles(
    plays: pd.DataFrame, team_roles: dict[str, TeamRoles], positions: dict[str, str]
) -> pd.Series:
    """Role of the targeted receiver on each play (NaN when there is no receiver)."""
    lookup = {(team, pid): role for team, tr in team_roles.items() for role, pid in tr.starters.items()}
    teams = plays["posteam"].to_numpy()
    rec = plays["receiver_player_id"].to_numpy()
    out = []
    for team, pid in zip(teams, rec):
        if not isinstance(pid, str):
            out.append(None)
            continue
        role = lookup.get((team, pid))
        if role is None:
            grp = position_group(positions.get(pid))
            role = grp if grp in ("WR", "TE", "RB") else "OTHER"
        out.append(role)
    return pd.Series(out, index=plays.index, dtype="object")


def tag_rusher_roles(plays: pd.DataFrame, positions: dict[str, str]) -> pd.Series:
    rus = plays["rusher_player_id"].to_numpy()
    out = []
    for pid in rus:
        if not isinstance(pid, str):
            out.append(None)
            continue
        grp = position_group(positions.get(pid))
        out.append(grp if grp in ("QB", "RB") else "OTHER")
    return pd.Series(out, index=plays.index, dtype="object")
