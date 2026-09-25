"""Download and cache the public nflverse data files.

Everything comes from nflverse (https://github.com/nflverse), which publishes
free play-by-play, charting, depth charts and schedules. Files are cached on
disk and re-downloaded once they are older than their TTL. If a download fails
we fall back to the cached copy so the app keeps working offline.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
import requests

from . import config

log = logging.getLogger(__name__)
_lock = threading.Lock()

PBP_COLUMNS = [
    "game_id", "play_id", "season", "season_type", "week", "game_date",
    "posteam", "defteam", "home_team", "away_team",
    "play_type", "down", "ydstogo", "yardline_100", "qtr", "half_seconds_remaining",
    "wp", "fixed_drive", "fixed_drive_result",
    "qb_dropback", "qb_scramble", "qb_kneel", "qb_spike", "two_point_attempt",
    "pass_attempt", "rush_attempt", "sack", "complete_pass", "interception",
    "yards_gained", "passing_yards", "receiving_yards", "rushing_yards",
    "air_yards", "yards_after_catch", "pass_length", "pass_location",
    "run_location", "run_gap",
    "passer_player_id", "passer_player_name",
    "receiver_player_id", "receiver_player_name",
    "rusher_player_id", "rusher_player_name",
    "touchdown", "pass_touchdown", "rush_touchdown", "td_team", "td_player_id",
    "third_down_converted", "third_down_failed",
    "epa", "success",
]


class DataUnavailable(Exception):
    pass


def _read(path: Path, columns: list[str]) -> pd.DataFrame:
    """Read only the columns we use; keeps memory low enough for small servers."""
    available = set(pq.read_schema(path).names)
    return pd.read_parquet(path, columns=[c for c in columns if c in available])


def _fetch(url: str, dest: Path, ttl_hours: float) -> Path | None:
    """Return a local path for url, downloading when missing or stale."""
    missing = dest.with_name(dest.name + ".missing")
    with _lock:
        fresh = dest.exists() and (time.time() - dest.stat().st_mtime) < ttl_hours * 3600
        if fresh:
            return dest
        if not dest.exists() and missing.exists() and (time.time() - missing.stat().st_mtime) < ttl_hours * 3600:
            return None  # recently confirmed as not published; don't ask again yet
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            log.info("Downloading %s", url)
            resp = requests.get(url, timeout=120)
            if resp.status_code == 404:
                log.info("Not published yet: %s", url)
                missing.touch()
                return dest if dest.exists() else None
            resp.raise_for_status()
            tmp = dest.with_suffix(dest.suffix + ".part")
            tmp.write_bytes(resp.content)
            tmp.replace(dest)
            missing.unlink(missing_ok=True)
            return dest
        except requests.RequestException as exc:
            if dest.exists():
                log.warning("Download failed (%s); using cached %s", exc, dest.name)
                return dest
            log.warning("Download failed and no cache for %s: %s", url, exc)
            return None


def _release(tag: str, filename: str, ttl_hours: float) -> Path | None:
    return _fetch(f"{config.NFLVERSE_RELEASES}/{tag}/{filename}", config.CACHE_DIR / filename, ttl_hours)


def _ttl(season: int) -> float:
    return config.TTL_CURRENT_HOURS if season >= config.current_season() else config.TTL_PRIOR_HOURS


def file_versions(season: int) -> tuple:
    """A cheap fingerprint of the cached inputs for a season, used to invalidate computed results."""
    names = [
        f"play_by_play_{season}.parquet",
        f"pbp_participation_{season}.parquet",
        f"ftn_charting_{season}.parquet",
        f"depth_charts_{season}.parquet",
        "players.parquet",
        "games.csv",
    ]
    out = []
    for n in names:
        p = config.CACHE_DIR / n
        out.append(p.stat().st_mtime if p.exists() else 0)
    return tuple(out)


def refresh_if_stale(season: int) -> None:
    """Re-download any of a season's files that are past their TTL (no-op when fresh)."""
    ttl = _ttl(season)
    _release("pbp", f"play_by_play_{season}.parquet", ttl)
    _release("pbp_participation", f"pbp_participation_{season}.parquet", ttl)
    _release("ftn_charting", f"ftn_charting_{season}.parquet", ttl)
    _fetch(config.SCHEDULE_URL, config.CACHE_DIR / "games.csv", config.TTL_SCHEDULE_HOURS)


def pbp(season: int) -> pd.DataFrame | None:
    path = _release("pbp", f"play_by_play_{season}.parquet", _ttl(season))
    if path is None:
        return None
    return _read(path, PBP_COLUMNS)


def participation(season: int) -> pd.DataFrame | None:
    """Coverage type, man/zone and pressure. nflverse publishes this after the season ends."""
    path = _release("pbp_participation", f"pbp_participation_{season}.parquet", _ttl(season))
    if path is None:
        return None
    cols = ["nflverse_game_id", "play_id", "defense_man_zone_type", "defense_coverage_type",
            "was_pressure", "number_of_pass_rushers", "time_to_throw"]
    return _read(path, cols)


def ftn(season: int) -> pd.DataFrame | None:
    """FTN charting: blitzers, pass rushers, play action, screens, motion. Updated weekly."""
    path = _release("ftn_charting", f"ftn_charting_{season}.parquet", _ttl(season))
    if path is None:
        return None
    cols = ["nflverse_game_id", "nflverse_play_id", "is_play_action", "is_screen_pass", "is_motion",
            "is_rpo", "n_blitzers", "n_pass_rushers", "n_defense_box", "is_drop"]
    return _read(path, cols)


def depth_charts(season: int) -> pd.DataFrame | None:
    """Daily ESPN depth chart snapshots collected by nflverse."""
    ttl = config.TTL_DEPTH_HOURS if season >= config.current_season() else config.TTL_PRIOR_HOURS
    path = _release("depth_charts", f"depth_charts_{season}.parquet", ttl)
    if path is None:
        return None
    df = _read(path, ["dt", "team", "player_name", "gsis_id", "pos_grp", "pos_name", "pos_abb", "pos_slot",
                      "pos_rank"])
    # Only the latest snapshot per team is used; drop the daily history right away.
    return df[df["dt"] == df.groupby("team")["dt"].transform("max")].reset_index(drop=True)


def injuries(season: int) -> pd.DataFrame | None:
    """Weekly injury reports (Out / Doubtful / Questionable)."""
    ttl = config.TTL_DEPTH_HOURS if season >= config.current_season() else config.TTL_PRIOR_HOURS
    path = _release("injuries", f"injuries_{season}.parquet", ttl)
    if path is None:
        return None
    return _read(path, ["season", "team", "week", "gsis_id", "full_name", "position", "report_status",
                        "practice_status", "report_primary_injury"])


def players() -> pd.DataFrame:
    path = _release("players", "players.parquet", config.TTL_PRIOR_HOURS)
    if path is None:
        raise DataUnavailable("Could not download the nflverse players file.")
    cols = ["gsis_id", "display_name", "short_name", "position", "jersey_number", "headshot", "latest_team"]
    return _read(path, cols).dropna(subset=["gsis_id"])


def schedule() -> pd.DataFrame:
    path = _fetch(config.SCHEDULE_URL, config.CACHE_DIR / "games.csv", config.TTL_SCHEDULE_HOURS)
    if path is None:
        raise DataUnavailable("Could not download the NFL schedule.")
    return pd.read_csv(path, low_memory=False)


def force_refresh() -> None:
    """Mark the current-season files stale so the next request downloads fresh copies.

    The files are kept (not deleted) so a failed download still falls back to them.
    """
    cur = config.current_season()
    for name in [
        f"play_by_play_{cur}.parquet",
        f"ftn_charting_{cur}.parquet",
        f"pbp_participation_{cur}.parquet",
        f"depth_charts_{cur}.parquet",
        f"injuries_{cur}.parquet",
        "games.csv",
    ]:
        p = config.CACHE_DIR / name
        if p.exists():
            os.utime(p, (0, 0))
        (config.CACHE_DIR / (name + ".missing")).unlink(missing_ok=True)
