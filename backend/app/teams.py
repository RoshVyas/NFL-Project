"""Static team info: names, colors and logo codes. Abbreviations follow nflverse."""
from __future__ import annotations

# abbr: (city, nickname, primary color, secondary color, espn logo code)
_TEAMS = {
    "ARI": ("Arizona", "Cardinals", "#97233F", "#000000", "ari"),
    "ATL": ("Atlanta", "Falcons", "#A71930", "#000000", "atl"),
    "BAL": ("Baltimore", "Ravens", "#241773", "#9E7C0C", "bal"),
    "BUF": ("Buffalo", "Bills", "#00338D", "#C60C30", "buf"),
    "CAR": ("Carolina", "Panthers", "#0085CA", "#101820", "car"),
    "CHI": ("Chicago", "Bears", "#0B162A", "#C83803", "chi"),
    "CIN": ("Cincinnati", "Bengals", "#FB4F14", "#000000", "cin"),
    "CLE": ("Cleveland", "Browns", "#311D00", "#FF3C00", "cle"),
    "DAL": ("Dallas", "Cowboys", "#003594", "#869397", "dal"),
    "DEN": ("Denver", "Broncos", "#FB4F14", "#002244", "den"),
    "DET": ("Detroit", "Lions", "#0076B6", "#B0B7BC", "det"),
    "GB": ("Green Bay", "Packers", "#203731", "#FFB612", "gb"),
    "HOU": ("Houston", "Texans", "#03202F", "#A71930", "hou"),
    "IND": ("Indianapolis", "Colts", "#002C5F", "#A2AAAD", "ind"),
    "JAX": ("Jacksonville", "Jaguars", "#006778", "#D7A22A", "jax"),
    "KC": ("Kansas City", "Chiefs", "#E31837", "#FFB81C", "kc"),
    "LA": ("Los Angeles", "Rams", "#003594", "#FFA300", "lar"),
    "LAC": ("Los Angeles", "Chargers", "#0080C6", "#FFC20E", "lac"),
    "LV": ("Las Vegas", "Raiders", "#000000", "#A5ACAF", "lv"),
    "MIA": ("Miami", "Dolphins", "#008E97", "#FC4C02", "mia"),
    "MIN": ("Minnesota", "Vikings", "#4F2683", "#FFC62F", "min"),
    "NE": ("New England", "Patriots", "#002244", "#C60C30", "ne"),
    "NO": ("New Orleans", "Saints", "#101820", "#D3BC8D", "no"),
    "NYG": ("New York", "Giants", "#0B2265", "#A71930", "nyg"),
    "NYJ": ("New York", "Jets", "#125740", "#FFFFFF", "nyj"),
    "PHI": ("Philadelphia", "Eagles", "#004C54", "#A5ACAF", "phi"),
    "PIT": ("Pittsburgh", "Steelers", "#101820", "#FFB612", "pit"),
    "SEA": ("Seattle", "Seahawks", "#002244", "#69BE28", "sea"),
    "SF": ("San Francisco", "49ers", "#AA0000", "#B3995D", "sf"),
    "TB": ("Tampa Bay", "Buccaneers", "#D50A0A", "#34302B", "tb"),
    "TEN": ("Tennessee", "Titans", "#0C2340", "#4B92DB", "ten"),
    "WAS": ("Washington", "Commanders", "#5A1414", "#FFB612", "wsh"),
}

# Older abbreviations that still appear in some files.
ALIASES = {"LAR": "LA", "WSH": "WAS", "JAC": "JAX", "OAK": "LV", "SD": "LAC", "STL": "LA"}


def normalize(abbr: str) -> str:
    abbr = (abbr or "").upper()
    return ALIASES.get(abbr, abbr)


def info(abbr: str) -> dict:
    abbr = normalize(abbr)
    city, nick, c1, c2, logo = _TEAMS[abbr]
    return {
        "abbr": abbr,
        "city": city,
        "name": nick,
        "full_name": f"{city} {nick}",
        "color": c1,
        "color2": c2,
        "logo": f"https://a.espncdn.com/i/teamlogos/nfl/500/{logo}.png",
    }


def all_teams() -> list[dict]:
    return [info(a) for a in sorted(_TEAMS)]


def is_team(abbr: str) -> bool:
    return normalize(abbr) in _TEAMS
