"""Bookmaker odds.

Live prices come from The Odds API (https://the-odds-api.com) when an API key is
set in the ODDS_API_KEY environment variable (or backend/.env). bet365 is not
one of its bookmakers, so bet365 prices are typed into the app by hand.

Without a key we fall back to the consensus spread / total / money line that
nflverse publishes in its schedule file.

Every price is normalised into a flat "quote":
    {"market", "player", "side", "line", "book", "book_title", "price"}
where side is "over" / "under" / "yes" / a team abbreviation, and price is decimal odds.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
import unicodedata
from datetime import datetime, timezone

import requests

from . import config, teams

log = logging.getLogger(__name__)

API_BASE = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl"
# Up to 10 bookmakers count as one "region" for The Odds API's credit usage.
BOOKMAKERS = ["paddypower", "williamhill", "skybet", "betfair_sb_uk", "ladbrokes_uk", "coral",
              "draftkings", "fanduel"]
MAIN_MARKETS = ["h2h", "spreads", "totals"]
PROP_MARKETS = ["player_pass_yds", "player_pass_tds", "player_rush_yds", "player_reception_yds",
                "player_receptions", "player_anytime_td", "player_1st_td"]
ODDS_TTL_MIN = 20
EVENTS_TTL_MIN = 60

_status: dict = {"remaining": None, "used": None, "error": None}


def _load_dotenv() -> None:
    env = config.BACKEND_DIR / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def api_key() -> str | None:
    _load_dotenv()
    key = os.environ.get("ODDS_API_KEY", "").strip()
    return key or None


def status() -> dict:
    return {"key_configured": api_key() is not None, **_status}


# ----------------------------------------------------------------------------
# Name matching
# ----------------------------------------------------------------------------

_SUFFIX = re.compile(r"\b(jr|sr|ii|iii|iv|v)\b")


def norm_name(name: str | None) -> str:
    if not name:
        return ""
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[.'\-]", " ", s)
    s = _SUFFIX.sub("", s)
    return " ".join(s.split())


FULL_NAMES = {t["full_name"]: t["abbr"] for t in teams.all_teams()}


def team_from_name(name: str) -> str | None:
    if name in FULL_NAMES:
        return FULL_NAMES[name]
    for full, abbr in FULL_NAMES.items():
        if full.split()[-1] == (name or "").split()[-1]:
            return abbr
    return None


# ----------------------------------------------------------------------------
# The Odds API
# ----------------------------------------------------------------------------

def _cache_path(name: str):
    return config.CACHE_DIR / "odds" / name


def _get(url: str, params: dict) -> requests.Response:
    resp = requests.get(url, params=params, timeout=30)
    _status["remaining"] = resp.headers.get("x-requests-remaining", _status["remaining"])
    _status["used"] = resp.headers.get("x-requests-used", _status["used"])
    return resp


def _cached_json(name: str, ttl_min: float, fetch, force: bool = False):
    path = _cache_path(name)
    if not force and path.exists() and time.time() - path.stat().st_mtime < ttl_min * 60:
        return json.loads(path.read_text()), path.stat().st_mtime
    data = fetch()
    if data is None:
        if path.exists():
            return json.loads(path.read_text()), path.stat().st_mtime
        return None, None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))
    return data, time.time()


def _events(key: str, force: bool = False):
    def fetch():
        r = _get(f"{API_BASE}/events", {"apiKey": key, "dateFormat": "iso"})
        if r.status_code != 200:
            _status["error"] = f"The Odds API returned {r.status_code}: {r.text[:160]}"
            return None
        return r.json()
    data, _ = _cached_json("events.json", EVENTS_TTL_MIN, fetch, force)
    return data or []


def _match_event(events: list, game: dict) -> dict | None:
    for ev in events:
        home = team_from_name(ev.get("home_team", ""))
        away = team_from_name(ev.get("away_team", ""))
        if {home, away} == {game["home"], game["away"]}:
            try:
                when = datetime.fromisoformat(ev["commence_time"].replace("Z", "+00:00"))
                gd = datetime.fromisoformat(game["gameday"]).replace(tzinfo=timezone.utc)
                if abs((when - gd).days) > 2:
                    continue
            except (KeyError, ValueError):
                pass
            return ev
    return None


def fetch_event_odds(game: dict, force: bool = False) -> tuple[dict | None, float | None]:
    key = api_key()
    if not key:
        return None, None
    _status["error"] = None
    try:
        ev = _match_event(_events(key, force), game)
        if not ev:
            _status["error"] = "This game isn't listed by The Odds API yet."
            return None, None

        def fetch():
            r = _get(f"{API_BASE}/events/{ev['id']}/odds", {
                "apiKey": key,
                "bookmakers": ",".join(BOOKMAKERS),
                "markets": ",".join(MAIN_MARKETS + PROP_MARKETS),
                "oddsFormat": "decimal",
                "dateFormat": "iso",
            })
            if r.status_code != 200:
                _status["error"] = f"The Odds API returned {r.status_code}: {r.text[:160]}"
                return None
            return r.json()

        return _cached_json(f"event_{ev['id']}.json", ODDS_TTL_MIN, fetch, force)
    except requests.RequestException as exc:
        _status["error"] = f"Couldn't reach The Odds API: {exc}"
        return None, None


def quotes_from_event(event: dict) -> list[dict]:
    """Flatten The Odds API event odds into quotes."""
    out = []
    for bk in event.get("bookmakers", []):
        for mk in bk.get("markets", []):
            market = mk.get("key")
            for oc in mk.get("outcomes", []):
                name, desc = oc.get("name"), oc.get("description")
                price, point = oc.get("price"), oc.get("point")
                if price is None:
                    continue
                q = {"market": market, "book": bk.get("key"), "book_title": bk.get("title", bk.get("key")),
                     "price": float(price), "line": point, "player": None, "side": None}
                if market in ("h2h", "spreads"):
                    q["side"] = team_from_name(name)
                elif market == "totals":
                    q["side"] = (name or "").lower()
                elif market in ("player_anytime_td", "player_1st_td"):
                    # Player is usually in "description" with name "Yes"; some books put the player in "name".
                    player = desc if desc else name
                    if (name or "").lower() == "no":
                        continue
                    q["player"], q["side"] = norm_name(player), "yes"
                else:
                    q["player"], q["side"] = norm_name(desc), (name or "").lower()
                if q["side"]:
                    out.append(q)
    return out


# ----------------------------------------------------------------------------
# Fallback: consensus lines from the schedule file
# ----------------------------------------------------------------------------

def american_to_decimal(a) -> float | None:
    try:
        a = float(a)
    except (TypeError, ValueError):
        return None
    if a != a or a == 0:
        return None
    return round(1 + (a / 100 if a > 0 else 100 / -a), 3)


def quotes_from_schedule(game: dict, row) -> list[dict]:
    """Spread / total / money line from nflverse's games.csv (US consensus)."""
    book, title = "consensus", "US consensus"
    out = []

    def add(market, side, line, price):
        dec = american_to_decimal(price)
        if dec:
            out.append({"market": market, "book": book, "book_title": title, "price": dec,
                        "line": line, "player": None, "side": side})

    add("h2h", game["home"], None, row.get("home_moneyline"))
    add("h2h", game["away"], None, row.get("away_moneyline"))
    sl = row.get("spread_line")
    if sl == sl and sl is not None:
        # nflverse spread_line is the home team's expected margin (positive = home favoured).
        sl = float(sl)
        hml, aml = american_to_decimal(row.get("home_moneyline")), american_to_decimal(row.get("away_moneyline"))
        if hml and aml and sl != 0 and (sl > 0) != (hml < aml):
            sl = -sl  # the sign disagrees with the money line favourite; trust the money line
        add("spreads", game["home"], -sl, row.get("home_spread_odds"))
        add("spreads", game["away"], sl, row.get("away_spread_odds"))
    tl = row.get("total_line")
    if tl == tl and tl is not None:
        add("totals", "over", float(tl), row.get("over_odds"))
        add("totals", "under", float(tl), row.get("under_odds"))
    return out
