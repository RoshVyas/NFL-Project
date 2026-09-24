from __future__ import annotations

import os
from datetime import date
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
CACHE_DIR = Path(os.environ.get("NFL_CACHE_DIR", BACKEND_DIR / "cache"))
USER_DATA_DIR = BACKEND_DIR / "user_data"
ROLE_OVERRIDES_FILE = USER_DATA_DIR / "role_overrides.json"
FRONTEND_DIST = BACKEND_DIR.parent / "frontend" / "dist"

NFLVERSE_RELEASES = "https://github.com/nflverse/nflverse-data/releases/download"
SCHEDULE_URL = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"

# How long a downloaded file is trusted before we fetch it again.
# Current-season files change after every game; last season's files rarely change.
TTL_CURRENT_HOURS = 3
TTL_PRIOR_HOURS = 24 * 7
TTL_SCHEDULE_HOURS = 3
TTL_DEPTH_HOURS = 6


def current_season(today: date | None = None) -> int:
    """NFL seasons start in September; Jan-Aug belong to the previous season."""
    today = today or date.today()
    return today.year if today.month >= 9 else today.year - 1


def seasons(today: date | None = None) -> tuple[int, int]:
    cur = current_season(today)
    return cur - 1, cur
