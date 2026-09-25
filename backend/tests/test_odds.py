"""Odds parsing and the bet finder's use of bookmaker prices, with a sample Odds API response."""
from app import finder, odds

SAMPLE_EVENT = {
    "id": "abc",
    "home_team": "Green Bay Packers",
    "away_team": "Atlanta Falcons",
    "commence_time": "2026-09-25T00:15:00Z",
    "bookmakers": [
        {"key": "paddypower", "title": "Paddy Power", "markets": [
            {"key": "h2h", "outcomes": [{"name": "Green Bay Packers", "price": 1.44},
                                        {"name": "Atlanta Falcons", "price": 2.9}]},
            {"key": "spreads", "outcomes": [{"name": "Green Bay Packers", "price": 1.91, "point": -4.5},
                                            {"name": "Atlanta Falcons", "price": 1.91, "point": 4.5}]},
            {"key": "totals", "outcomes": [{"name": "Over", "price": 1.9, "point": 43.5},
                                           {"name": "Under", "price": 1.9, "point": 43.5}]},
            {"key": "player_reception_yds", "outcomes": [
                {"name": "Over", "description": "Christian Watson", "price": 1.83, "point": 55.5},
                {"name": "Under", "description": "Christian Watson", "price": 1.95, "point": 55.5}]},
            {"key": "player_anytime_td", "outcomes": [
                {"name": "Yes", "description": "Bijan Robinson", "price": 1.8}]},
        ]},
        {"key": "draftkings", "title": "DraftKings", "markets": [
            {"key": "player_reception_yds", "outcomes": [
                {"name": "Over", "description": "Christian Watson", "price": 1.87, "point": 55.5},
                {"name": "Under", "description": "Christian Watson", "price": 1.91, "point": 55.5}]},
        ]},
    ],
}


def test_quotes_parse_all_markets():
    q = odds.quotes_from_event(SAMPLE_EVENT)
    assert {x["market"] for x in q} == {"h2h", "spreads", "totals", "player_reception_yds", "player_anytime_td"}
    ml = [x for x in q if x["market"] == "h2h"]
    assert {x["side"] for x in ml} == {"GB", "ATL"}
    watson = [x for x in q if x["player"] == "christian watson" and x["side"] == "over"]
    assert {x["book"] for x in watson} == {"paddypower", "draftkings"}
    assert all(x["line"] == 55.5 for x in watson)
    bijan = [x for x in q if x["market"] == "player_anytime_td"]
    assert bijan[0]["player"] == "bijan robinson" and bijan[0]["side"] == "yes"


def test_prices_prefer_paddy_power_and_find_best():
    q = [x for x in odds.quotes_from_event(SAMPLE_EVENT) if x["player"] == "christian watson" and x["side"] == "over"]
    pr = finder._prices(q)
    assert pr["paddypower"] == 1.83
    assert pr["best"] == {"book": "DraftKings", "price": 1.87}


def test_no_vig_probability():
    p = finder._no_vig([1.91], [1.91])
    assert abs(p - 0.5) < 1e-9


def test_name_normalisation():
    assert odds.norm_name("Michael Penix Jr.") == "michael penix"
    assert odds.norm_name("Ja'Marr Chase") == "ja marr chase"
    assert odds.norm_name("Kenneth Walker III") == "kenneth walker"


def test_schedule_fallback_fixes_flipped_spread():
    game = {"home": "MIA", "away": "KC"}
    row = {"home_moneyline": 470, "away_moneyline": -650, "spread_line": 10.5, "home_spread_odds": -110,
           "away_spread_odds": -110, "total_line": 45.5, "over_odds": -110, "under_odds": -110}
    q = odds.quotes_from_schedule(game, row)
    home_spread = next(x for x in q if x["market"] == "spreads" and x["side"] == "MIA")
    assert home_spread["line"] == 10.5  # Miami are the underdog, so they get the points


def test_probability_helpers():
    assert abs(finder.p_over({"type": "normal", "mean": 50, "sd": 10}, 50) - 0.5) < 1e-9
    # Poisson mean 1: P(X >= 2) = 1 - e^-1 * 2
    assert abs(finder.p_over({"type": "poisson", "mean": 1.0}, 1.5) - (1 - 2 * 2.718281828 ** -1)) < 1e-6
