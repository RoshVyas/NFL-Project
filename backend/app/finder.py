"""Bet finder: turn the matchup stats into probabilities, fair odds and picks.

How it works, in plain terms:

1. Project the game. Each team's expected points = its scoring rate x what the
   opponent allows, relative to the league (last season and this season blended,
   with this season counting more as games are played), plus home field.
2. Project every relevant player: yards, receptions and touchdowns per game from
   his own form, adjusted by what the opponent allows to his role (X, Z, slot, TE,
   RB, QB). Players ruled Out or Doubtful on the injury report are skipped.
3. Turn projections into probabilities (normal curve for yards, Poisson for
   counts and touchdowns) and blend them with the bookmakers' own view, so one
   noisy stat can't create a fake edge. The blend weight depends on how much data
   this game has, which is why the formula shifts from game to game.
4. Value = probability x odds - 1. Picks are ranked by value x confidence, where
   confidence reflects sample size, how strongly the matchup stats agree, and
   whether the price is a real Paddy Power quote or a reference/estimate.
"""
from __future__ import annotations

import math
from datetime import datetime

import pandas as pd

from . import config, odds as odds_mod, report, sources, teams
from .roles import position_group

HOME_EDGE = 1.5          # points
SD_MARGIN = 13.0
SD_TOTAL = 13.5
SD_TEAM = 9.5
K_TEAM = 4               # this season counts as much as last season after 4 games
K_PLAYER = 4
DEF_ST_TD_PER_TEAM = 0.1  # defensive / special teams TDs per team-game
BOOK_MARGIN = 1.05       # typical bookmaker overround on a two-way prop
# How much the model's own probability counts against the market's (the rest is the market).
MODEL_WEIGHT = {"main": 0.45, "prop": 0.6, "td": 0.65}

MARKET_LABELS = {
    "h2h": "Money line", "spreads": "Spread", "totals": "Total points", "team_totals": "Team total",
    "player_pass_yds": "Passing yards", "player_pass_tds": "Passing TDs", "player_rush_yds": "Rushing yards",
    "player_reception_yds": "Receiving yards", "player_receptions": "Receptions",
    "player_anytime_td": "Anytime TD scorer", "player_1st_td": "First TD scorer",
}
UNITS = {"player_pass_yds": "passing yards", "player_pass_tds": "passing TDs", "player_rush_yds": "rushing yards",
         "player_reception_yds": "receiving yards", "player_receptions": "receptions"}


# ----------------------------------------------------------------------------
# Maths
# ----------------------------------------------------------------------------

def norm_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def poisson_cdf(k: int, lam: float) -> float:
    if lam <= 0:
        return 1.0
    term, total = math.exp(-lam), math.exp(-lam)
    for i in range(1, k + 1):
        term *= lam / i
        total += term
    return min(1.0, total)


def p_over(dist: dict, line: float) -> float:
    if dist["type"] == "normal":
        return 1 - norm_cdf((line - dist["mean"]) / dist["sd"])
    # Poisson: over x.5 means at least floor(x.5)+1
    return 1 - poisson_cdf(math.floor(line), dist["mean"])


def fair(p: float | None) -> float | None:
    return round(1 / p, 2) if p and p > 0 else None


def blend(prior, cur, w):
    if prior is None:
        return cur
    if cur is None:
        return prior
    return prior * (1 - w) + cur * w


def _get(sd, side, team, key):
    if not sd.available or not sd.games.get(team):
        return None
    src = sd.off if side == "off" else sd.deff
    return src.get(team, {}).get(key)


def _league(sd, side, key):
    if not sd.available:
        return None
    src = sd.off if side == "off" else sd.deff
    vals = [m.get(key) for t, m in src.items() if sd.games.get(t) and m.get(key) is not None]
    return sum(vals) / len(vals) if vals else None


# ----------------------------------------------------------------------------
# Model
# ----------------------------------------------------------------------------

class Model:
    def __init__(self, game: dict):
        self.game = game
        prior, cur = config.seasons()
        self.pri = report.get_season(prior)
        self.cur = report.get_season(cur)
        self.sds = [self.pri, self.cur]
        self.depth = report.get_depth(cur)
        self.home, self.away = game["home"], game["away"]
        self.injuries = self._injuries()
        self.edges = {
            self.away: {e["key"]: e for e in report.edges(self.away, self.home, self.sds, self.depth)},
            self.home: {e["key"]: e for e in report.edges(self.home, self.away, self.sds, self.depth)},
        }

    # --- weights ---------------------------------------------------------
    def w_team(self, team):
        g = self.cur.games.get(team, 0) if self.cur.available else 0
        return g / (g + K_TEAM)

    def blended(self, side, team, key):
        return blend(_get(self.pri, side, team, key), _get(self.cur, side, team, key), self.w_team(team))

    def league(self, side, key, team):
        return blend(_league(self.pri, side, key), _league(self.cur, side, key), self.w_team(team))

    def factor(self, opp, key, strength=0.5):
        """How much the opponent defense inflates (>1) or suppresses (<1) a stat vs the league."""
        allowed, lg = self.blended("def", opp, key), self.league("def", key, opp)
        if not allowed or not lg:
            return 1.0
        return max(0.7, min(1.35, 1 + strength * (allowed / lg - 1)))

    # --- injuries --------------------------------------------------------
    def _injuries(self) -> dict:
        df = sources.injuries(config.current_season())
        if df is None or df.empty:
            return {}
        df = df.copy()
        df["team"] = df["team"].map(teams.normalize)
        df = df[df["team"].isin([self.home, self.away])]
        if df.empty:
            return {}
        latest = df.groupby("team")["week"].transform("max")
        df = df[(df["week"] == latest) & df["report_status"].notna()]
        return {r.gsis_id: {"status": r.report_status, "name": r.full_name, "team": r.team,
                            "pos": r.position, "injury": r.report_primary_injury}
                for r in df.itertuples() if isinstance(r.gsis_id, str)}

    # --- teams -------------------------------------------------------------
    def team_points(self, team, opp, is_home):
        off, de = self.blended("off", team, "points_pg"), self.blended("def", opp, "points_pg")
        lg = self.league("off", "points_pg", team) or 22.0
        exp = off * de / lg if off and de else lg
        exp = lg + 0.85 * (exp - lg)
        return exp + (HOME_EDGE / 2 if is_home else -HOME_EDGE / 2)

    def td_per_point(self, team):
        tds = self.league("off", "pass_td_pg", team) or 0
        tds += self.league("off", "rush_td_pg", team) or 0
        pts = self.league("off", "points_pg", team) or 22.0
        return tds / pts if tds else 0.105

    # --- players -----------------------------------------------------------
    def _rows(self, sd, pid):
        if not sd.available or sd.players is None:
            return None
        rows = sd.players[sd.players["player_id"] == pid]
        return rows if len(rows) else None

    def _share_parts(self, sd, rows):
        """(TD share, team TDs, red-zone share, team red-zone chances) across the teams a player was on."""
        if rows is None or not sd.available:
            return None
        td = team_td = rz = team_rz = 0.0
        for r in rows.itertuples():
            tp = sd.players[sd.players["team"] == r.team]
            td += r.total_td
            team_td += tp["total_td"].sum()
            rz += r.rz_tgts + r.rz_carries
            team_rz += (tp["rz_tgts"] + tp["rz_carries"]).sum()
        return (td / team_td if team_td else None, team_td, rz / team_rz if team_rz else None, team_rz)

    def td_share(self, rows_p, rows_c):
        """Share of team TDs: 40% actual TD share, 60% red-zone opportunity share (steadier).

        Each season is weighted by how many TDs / red-zone chances it contains, so two games
        of data can't swing it much.
        """
        a, b = self._share_parts(self.pri, rows_p), self._share_parts(self.cur, rows_c)
        td_p, _, rz_p, _ = a if a else (None, 0, None, 0)
        td_c, n_td, rz_c, n_rz = b if b else (None, 0, None, 0)
        td = blend(td_p, td_c, n_td / (n_td + 12))
        rz = blend(rz_p, rz_c, n_rz / (n_rz + 25))
        if td is None and rz is None:
            return 0.0
        return 0.4 * (td if td is not None else rz) + 0.6 * (rz if rz is not None else td)

    def player(self, pid, team, opp, slot_label=None):
        rows_p, rows_c = self._rows(self.pri, pid), self._rows(self.cur, pid)
        if rows_p is None and rows_c is None:
            return None
        g_p = int(rows_p["games"].sum()) if rows_p is not None else 0
        g_c = int(rows_c["games"].sum()) if rows_c is not None else 0
        w = g_c / (g_c + K_PLAYER) if g_c else 0.0

        def rate(col):
            vp = rows_p[col].sum() / g_p if rows_p is not None and g_p else None
            vc = rows_c[col].sum() / g_c if rows_c is not None and g_c else None
            return blend(vp, vc, w) or 0.0

        any_rows = rows_c if rows_c is not None else rows_p
        pos = position_group(any_rows["position"].iloc[0])
        name = any_rows["name"].iloc[0]
        tr = self.cur.team_roles.get(team) if self.cur.available else None
        role = (tr.role_of(pid) if tr else None) or pos
        rec_key = {"X": "X", "Z": "Z", "SLOT": "SLOT", "TE": "TE", "RB": "RB"}.get(role, "WR")

        f_rec = self.factor(opp, f"rec_yds_pg_{rec_key}")
        f_recs = self.factor(opp, f"rec_pg_{rec_key}")
        f_rush = self.factor(opp, "qb_rush_yds_pg" if pos == "QB" else "ALLRB_rush_yds_pg")
        f_pass = self.factor(opp, "pass_yds_pg")
        f_ptd = self.factor(opp, "pass_td_pg")

        share = self.td_share(rows_p, rows_c)
        rush_share = None
        if pos == "QB":
            # A QB's anytime-TD chance comes from his rushing TDs only.
            rtd = rate("rush_td")
            rush_share = share * (rtd / rate("total_td")) if rate("total_td") else 0.02
        inj = self.injuries.get(pid)
        return {
            "id": pid, "name": name, "team": team, "opp": opp, "pos": pos, "role": role,
            "slot_label": slot_label, "games_prior": g_p, "games_cur": g_c, "w_cur": round(w, 2),
            "rec_yds": rate("rec_yds") * f_rec, "rec": rate("rec") * f_recs, "targets": rate("targets"),
            "rush_yds": rate("rush_yds") * f_rush, "carries": rate("carries"),
            "pass_yds": rate("pass_yds") * f_pass, "pass_td": rate("pass_td") * f_ptd,
            "base": {"rec_yds": rate("rec_yds"), "rec": rate("rec"), "rush_yds": rate("rush_yds"),
                     "pass_yds": rate("pass_yds"), "pass_td": rate("pass_td")},
            "factors": {"rec": f_rec, "rush": f_rush, "pass": f_pass},
            "td_share": rush_share if pos == "QB" else share,
            "injury": inj,
        }

    def players(self, team, opp):
        """Starters from the depth chart plus anyone with real usage this season."""
        lineup = report.lineup_ids(self.depth, team)
        wanted: dict[str, str] = {}
        for slot in ("QB1", "RB1", "RB2", "X", "Z", "SLOT", "TE1", "TE2"):
            pid = report.resolve_player(slot, self.cur, team, lineup)
            if pid:
                wanted.setdefault(pid, slot)
        if self.cur.available and self.cur.players is not None:
            tp = self.cur.players[self.cur.players["team"] == team]
            for r in tp.itertuples():
                if r.tgt_share >= 8 or (r.carries >= 3 * max(1, r.games) and position_group(r.position) == "RB"):
                    wanted.setdefault(r.player_id, None)
        out = []
        for pid, slot in wanted.items():
            p = self.player(pid, team, opp, slot)
            if p:
                out.append(p)
        return out


# ----------------------------------------------------------------------------
# Selections
# ----------------------------------------------------------------------------

def _sel(id_, market, label, p_model, dist=None, **kw):
    return {"id": id_, "market": market, "market_label": MARKET_LABELS.get(market, market), "label": label,
            "p_model": p_model, "dist": dist, **kw}


def _group_quotes(quotes, market, player=None, side=None, line=None):
    out = []
    for q in quotes:
        if q["market"] != market:
            continue
        if player is not None and q["player"] != player:
            continue
        if side is not None and q["side"] != side:
            continue
        if line is not None and q["line"] is not None and abs(q["line"] - line) > 1e-6:
            continue
        out.append(q)
    return out


def _pick_line(qs):
    """Paddy Power's line if they have one, otherwise the most common line."""
    pp = [q["line"] for q in qs if q["book"] == "paddypower" and q["line"] is not None]
    if pp:
        return pp[0]
    lines = [q["line"] for q in qs if q["line"] is not None]
    return max(set(lines), key=lines.count) if lines else None


def _no_vig(p_side_prices: list[float], p_other_prices: list[float]) -> float | None:
    if not p_side_prices or not p_other_prices:
        return None
    a = sum(1 / x for x in p_side_prices) / len(p_side_prices)
    b = sum(1 / x for x in p_other_prices) / len(p_other_prices)
    return a / (a + b)


def _prices(qs):
    pp = next((q["price"] for q in qs if q["book"] == "paddypower"), None)
    best = max(qs, key=lambda q: q["price"]) if qs else None
    return {
        "paddypower": pp,
        "best": {"book": best["book_title"], "price": best["price"]} if best else None,
        "all": sorted([{"book": q["book_title"], "price": q["price"]} for q in qs], key=lambda x: -x["price"]),
    }


def build(game: dict, force_odds: bool = False) -> dict:
    m = Model(game)
    home, away = m.home, m.away

    # ---- odds ---------------------------------------------------------------
    event, fetched = odds_mod.fetch_event_odds(game, force_odds)
    quotes = odds_mod.quotes_from_event(event) if event else []
    source = "the-odds-api" if quotes else "schedule"
    if not any(q["market"] in ("h2h", "spreads", "totals") for q in quotes):
        sched = sources.schedule()
        row = sched[sched["game_id"] == game["game_id"]]
        if len(row):
            quotes += odds_mod.quotes_from_schedule(game, row.iloc[0].to_dict())
    books = sorted({q["book_title"] for q in quotes})

    # ---- team projections -----------------------------------------------------
    exp_home = m.team_points(home, away, True)
    exp_away = m.team_points(away, home, False)
    margin, total = exp_home - exp_away, exp_home + exp_away
    trust_team = 0.7 + 0.3 * min(1, (m.cur.games.get(home, 0) + m.cur.games.get(away, 0)) / 12)
    wm_main = MODEL_WEIGHT["main"] * trust_team

    sels = []

    # Money line
    ml_home = norm_cdf(margin / SD_MARGIN)
    for team, p in ((home, ml_home), (away, 1 - ml_home)):
        other = away if team == home else home
        qs, qo = _group_quotes(quotes, "h2h", side=team), _group_quotes(quotes, "h2h", side=other)
        mk = _no_vig([q["price"] for q in qs], [q["price"] for q in qo])
        sels.append(_sel(f"ml-{team}", "h2h", f"{teams.info(team)['name']} to win", p,
                         p_market=mk, weight=wm_main, quotes=qs, team=team, kind="main"))

    # Spread
    sq = _group_quotes(quotes, "spreads", side=home)
    line_home = _pick_line(sq)
    if line_home is not None:
        p_home_cover = norm_cdf((margin + line_home) / SD_MARGIN)
        for team, line, p in ((home, line_home, p_home_cover), (away, -line_home, 1 - p_home_cover)):
            other = away if team == home else home
            qs = _group_quotes(quotes, "spreads", side=team, line=line)
            qo = _group_quotes(quotes, "spreads", side=other, line=-line)
            mk = _no_vig([q["price"] for q in qs], [q["price"] for q in qo])
            sels.append(_sel(f"sp-{team}", "spreads", f"{teams.info(team)['name']} {line:+g}", p,
                             dist={"type": "normal", "mean": margin if team == home else -margin, "sd": SD_MARGIN,
                                   "kind": "spread"},
                             line=line, p_market=mk, weight=wm_main, quotes=qs, team=team, kind="main"))

    # Total
    tq = _group_quotes(quotes, "totals")
    tline = _pick_line(tq)
    if tline is not None:
        dist = {"type": "normal", "mean": total, "sd": SD_TOTAL}
        po = p_over(dist, tline)
        for side, p in (("over", po), ("under", 1 - po)):
            qs = _group_quotes(quotes, "totals", side=side, line=tline)
            qo = _group_quotes(quotes, "totals", side="under" if side == "over" else "over", line=tline)
            mk = _no_vig([q["price"] for q in qs], [q["price"] for q in qo])
            sels.append(_sel(f"tot-{side}", "totals", f"{side.title()} {tline:g} total points", p, dist=dist,
                             line=tline, side=side, p_market=mk, weight=wm_main, quotes=qs, kind="main"))

    # Team totals (implied from the market total and spread when no team-total price exists)
    if tline is not None and line_home is not None:
        for team, exp, implied in ((home, exp_home, (tline - line_home) / 2),
                                   (away, exp_away, (tline + line_home) / 2)):
            tl = math.floor(implied) + 0.5
            dist = {"type": "normal", "mean": exp, "sd": SD_TEAM}
            po = p_over(dist, tl)
            side, p = ("over", po) if po >= 0.5 else ("under", 1 - po)
            sels.append(_sel(f"tt-{team}-{side}", "team_totals",
                             f"{teams.info(team)['name']} {side} {tl:g} points", p, dist=dist, line=tl, side=side,
                             p_market=0.5, weight=wm_main, quotes=[], team=team, kind="main", est_line=True,
                             est_price=round(2 / BOOK_MARGIN, 2)))

    # ---- players -----------------------------------------------------------------
    team_td = {home: exp_home * m.td_per_point(home), away: exp_away * m.td_per_point(away)}
    players = m.players(home, away) + m.players(away, home)
    out_players = []
    active = []
    for p in players:
        st = (p["injury"] or {}).get("status")
        if st in ("Out", "Doubtful"):
            out_players.append(p)
            continue
        active.append(p)
        # TD rate: team's expected offensive TDs x the player's share, nudged by the matchup.
        f_td = p["factors"]["rush"] if p["pos"] in ("RB", "QB") else p["factors"]["rec"]
        p["td_lambda"] = team_td[p["team"]] * p["td_share"] * (1 + 0.5 * (f_td - 1))

    total_lambda = sum(team_td.values()) + 2 * DEF_ST_TD_PER_TEAM
    p_any_td_in_game = 1 - math.exp(-total_lambda)

    for p in active:
        trust = 0.65 + 0.35 * min(1, (p["games_cur"] * 2 + p["games_prior"]) / 14)
        if (p["injury"] or {}).get("status") == "Questionable":
            trust *= 0.8
        p["trust"] = trust
        pname = odds_mod.norm_name(p["name"])
        edge_key = _edge_key(p)
        props = []
        if p["pos"] == "QB":
            props += [("player_pass_yds", p["pass_yds"], p["base"]["pass_yds"], "normal", max(0.24 * p["pass_yds"], 45)),
                      ("player_pass_tds", p["pass_td"], p["base"]["pass_td"], "poisson", None)]
            if p["rush_yds"] >= 15:
                props.append(("player_rush_yds", p["rush_yds"], p["base"]["rush_yds"], "normal",
                              max(0.55 * p["rush_yds"], 12)))
        else:
            if p["rush_yds"] >= 20:
                props.append(("player_rush_yds", p["rush_yds"], p["base"]["rush_yds"], "normal",
                              max(0.5 * p["rush_yds"], 12)))
            if p["rec_yds"] >= 12:
                props.append(("player_reception_yds", p["rec_yds"], p["base"]["rec_yds"], "normal",
                              max(0.62 * p["rec_yds"], 14)))
            if p["rec"] >= 1.5:
                props.append(("player_receptions", p["rec"], p["base"]["rec"], "poisson", None))

        for market, mean, base, dtype, sd in props:
            dist = {"type": dtype, "mean": mean} | ({"sd": sd} if sd else {})
            qs_all = _group_quotes(quotes, market, player=pname)
            line = _pick_line(qs_all)
            est = line is None
            if est:
                line = math.floor(base) + 0.5 if base >= 1 else 0.5
            po = p_over(dist, line)
            side, prob = ("over", po) if po >= 0.5 else ("under", 1 - po)
            other = "under" if side == "over" else "over"
            qs = _group_quotes(quotes, market, player=pname, side=side, line=line)
            qo = _group_quotes(quotes, market, player=pname, side=other, line=line)
            if est:
                # No bookmaker line: price it the way a book would, from the player's own average
                # (no matchup adjustment) plus a normal margin. Value then only comes from the matchup.
                base_dist = dict(dist, mean=base) | ({"sd": sd * base / mean} if sd and mean else {})
                pb = p_over(base_dist, line)
                mk = pb if side == "over" else 1 - pb
            else:
                mk = _no_vig([q["price"] for q in qs], [q["price"] for q in qo])
            sels.append(_sel(f"{market}-{p['id']}-{side}", market,
                             f"{p['name']} {side} {line:g} {UNITS[market]}", prob, dist=dist | {"proj": round(mean, 1)},
                             line=line, side=side, player=p["name"], player_id=p["id"], team=p["team"],
                             p_market=mk, weight=MODEL_WEIGHT["prop"] * trust, quotes=qs, kind="prop",
                             est_price=round(1 / max(0.05, min(0.95, mk)) / BOOK_MARGIN, 2) if est else None,
                             est_line=est, edge_key=edge_key, reasons=_reasons(m, p, market, side)))

        # Anytime / first TD
        lam = p["td_lambda"]
        p_any = 1 - math.exp(-lam)
        qa = _group_quotes(quotes, "player_anytime_td", player=pname)
        p["p_any"] = p_any
        p["p_first"] = (lam / total_lambda) * p_any_td_in_game if total_lambda else 0
        sels.append(_sel(f"atd-{p['id']}", "player_anytime_td", f"{p['name']} anytime TD", p_any,
                         dist={"type": "poisson_any", "mean": lam}, player=p["name"], player_id=p["id"],
                         team=p["team"], p_market=None, weight=MODEL_WEIGHT["td"] * trust, quotes=qa,
                         kind="td", edge_key="rz", reasons=_td_reasons(m, p)))

    # ---- finish selections: blend with market, price, value -----------------------
    for s in sels:
        s["p"] = _final_p(s)
        pr = _prices(s.pop("quotes"))
        s["prices"] = pr
        if pr["paddypower"]:
            s["price_used"], s["price_source"] = pr["paddypower"], "Paddy Power"
        elif pr["best"]:
            s["price_used"], s["price_source"] = pr["best"]["price"], pr["best"]["book"]
        elif s.get("est_price"):
            s["price_used"], s["price_source"] = s["est_price"], "estimated"
        else:
            s["price_used"], s["price_source"] = None, None
        s["fair_odds"] = fair(s["p"])
        s["ev"] = round(s["p"] * s["price_used"] - 1, 3) if s["price_used"] else None
        s["confidence"] = round(_confidence(s, m), 3)
        s["score"] = round((s["ev"] if s["ev"] is not None else -1) * s["confidence"], 4)
        s["p"] = round(s["p"], 4)
        s["p_model"] = round(s["p_model"], 4)

    singles = _pick_singles(sels)
    value_bb = _builder(sels, lambda s: s["p"] >= 0.55 and s["ev"] is not None and s["ev"] >= 0,
                        min_legs=3, max_legs=4, target=None)
    long_bb = _builder(sels, lambda s: 0.22 <= s["p"] <= 0.62 and s["ev"] is not None and s["ev"] >= 0,
                       min_legs=3, max_legs=5, target=12.0)

    td_rows = []
    for p in sorted(active, key=lambda x: -x["p_any"]):
        pname = odds_mod.norm_name(p["name"])
        atd = next(s for s in sels if s["id"] == f"atd-{p['id']}")
        first_prices = _prices(_group_quotes(quotes, "player_1st_td", player=pname))
        td_rows.append({
            "player": p["name"], "player_id": p["id"], "team": p["team"], "role": p["role"],
            "p_any": round(atd["p"], 4), "fair_any": fair(atd["p"]), "prices_any": atd["prices"],
            "ev_any": atd["ev"],
            "p_first": round(p["p_first"], 4), "fair_first": fair(p["p_first"]), "prices_first": first_prices,
            "ev_first": round(p["p_first"] * first_prices["paddypower"] - 1, 3) if first_prices["paddypower"] else None,
            "reasons": atd["reasons"], "injury": p["injury"],
        })
    first_td = sorted(td_rows, key=lambda r: -r["p_first"])[:3]

    return report.json_safe({
        "game": game,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "odds": {
            "source": source, **odds_mod.status(), "books": books,
            "fetched_at": datetime.fromtimestamp(fetched).isoformat(timespec="seconds") if fetched else None,
            "bet365_note": "bet365 isn't available from The Odds API. Type its prices into the bet365 boxes.",
        },
        "projection": {
            "home": home, "away": away, "home_pts": round(exp_home, 1), "away_pts": round(exp_away, 1),
            "margin": round(margin, 1), "total": round(total, 1), "home_win": round(ml_home, 3),
            "market_spread_home": line_home, "market_total": tline,
            "home_tds": round(team_td[home], 2), "away_tds": round(team_td[away], 2),
        },
        "singles": singles,
        "value_builder": value_bb,
        "longshot_builder": long_bb,
        "td_top3": td_rows[:3],
        "first_td": first_td,
        "td_all": td_rows[:12],
        "all": sorted(sels, key=lambda s: -s["score"])[:40],
        "players": [_player_summary(p) for p in active],
        "unavailable": [{"name": p["name"], "team": p["team"], "pos": p["pos"], **(p["injury"] or {})}
                        for p in out_players],
        "injuries": list(m.injuries.values()),
        "weights": {
            "model_weight_main": round(wm_main, 2), "team_trust": round(trust_team, 2),
            "current_season_weight": {home: round(m.w_team(home), 2), away: round(m.w_team(away), 2)},
        },
    })


def _final_p(s):
    """Blend the model's probability with the market's no-vig probability."""
    pm, mk, w = s["p_model"], s.get("p_market"), s.get("weight", 0.6)
    if mk is None:
        return pm
    return w * pm + (1 - w) * mk


def _edge_key(p):
    if p["pos"] == "QB":
        return "pass_eff"
    if p["pos"] == "RB":
        return "RB_rush"
    return {"X": "X", "Z": "Z", "SLOT": "SLOT", "TE": "TE"}.get(p["role"])


def _confidence(s, m):
    c = 1.0
    team = s.get("team")
    ek = s.get("edge_key")
    if team and ek:
        e = m.edges.get(team, {}).get(ek)
        if e:
            agree = e["score"] - 0.5
            c *= 1 + 0.4 * (agree if s.get("side", "over") in ("over", None, "yes") else -agree)
    c *= {"Paddy Power": 1.0, "estimated": 0.7, None: 0.5}.get(s.get("price_source"), 0.9)
    c *= s.get("weight", 0.6) / 0.6 if s["kind"] == "prop" else 1.0
    return max(0.2, min(1.5, c))


def _conflicts(a, b):
    if a.get("player_id") and a.get("player_id") == b.get("player_id") and a["market"] == b["market"]:
        return True
    if a["market"] == b["market"] and a["kind"] == "main":
        return True
    return False


def _pick_singles(sels, n=5):
    pool = [s for s in sels if s["price_used"] and s["p"] >= 0.42 and s["price_used"] <= 5.0]
    pool.sort(key=lambda s: -s["score"])
    out, per_player = [], {}
    for s in pool:
        if any(_conflicts(s, o) for o in out):
            continue
        pid = s.get("player_id")
        if pid and per_player.get(pid, 0) >= 2:
            continue
        if s["kind"] == "main" and sum(o["kind"] == "main" for o in out) >= 2:
            continue
        out.append(s)
        if pid:
            per_player[pid] = per_player.get(pid, 0) + 1
        if len(out) == n:
            break
    for s in out:
        s["value_flag"] = "value" if (s["ev"] or 0) > 0.02 else "thin"
    return out


def _builder(sels, keep, min_legs, max_legs, target):
    pool = sorted([s for s in sels if keep(s) and s["price_used"]], key=lambda s: -s["score"])
    legs = []
    for s in pool:
        if any(_conflicts(s, o) or (s.get("player_id") and s.get("player_id") == o.get("player_id")) for o in legs):
            continue
        if s["kind"] == "main" and any(o["kind"] == "main" for o in legs):
            continue
        legs.append(s)
        price = math.prod(l["price_used"] for l in legs)
        if len(legs) >= max_legs or (target and len(legs) >= min_legs and price >= target) or \
                (not target and len(legs) >= min_legs and len(legs) >= 3 and price >= 3.0):
            break
    if len(legs) < min_legs:
        return None
    p = math.prod(l["p"] for l in legs)
    price = math.prod(l["price_used"] for l in legs)
    return {"legs": legs, "p": round(p, 4), "fair_odds": fair(p), "price": round(price, 2),
            "ev": round(p * price - 1, 3),
            "note": "Leg prices multiplied together, assuming the legs are independent. bet365 prices bet "
                    "builders with its own adjustments, so type its builder price in to check the value."}


def _fmt_rank(r):
    return f"{r}{'th' if 10 <= r % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(r % 10, 'th')}" if r else "?"


def _reasons(m, p, market, side):
    out = []
    cur = str(m.cur.season)
    opp = p["opp"]
    opp_name = teams.info(opp)["name"]
    proj_key = {"player_reception_yds": "rec_yds", "player_receptions": "rec", "player_rush_yds": "rush_yds",
                "player_pass_yds": "pass_yds", "player_pass_tds": "pass_td"}[market]
    out.append(f"Projection {p[proj_key]:.1f} vs his average of {p['base'][proj_key]:.1f} "
               f"({p['games_cur']} games this season, {p['games_prior']} last season)")
    role_key = {"X": "X", "Z": "Z", "SLOT": "SLOT", "TE": "TE", "RB": "RB"}.get(p["role"], "WR")
    key = {"player_reception_yds": f"rec_yds_pg_{role_key}", "player_receptions": f"rec_pg_{role_key}",
           "player_rush_yds": "qb_rush_yds_pg" if p["pos"] == "QB" else "ALLRB_rush_yds_pg",
           "player_pass_yds": "pass_yds_pg", "player_pass_tds": "pass_td_pg"}[market]
    for sd in m.sds:
        if not sd.available or not sd.games.get(opp):
            continue
        v, r = sd.deff[opp].get(key), sd.def_rank.get(opp, {}).get(key)
        if v is not None:
            out.append(f"{opp_name} allow {v:.1f} per game here in {sd.season} ({_fmt_rank(r)} of 32)")
    if p["injury"]:
        out.append(f"Listed {p['injury']['status']} ({p['injury'].get('injury') or 'injury'})")
    return out


def _td_reasons(m, p):
    out = [f"{p['td_share'] * 100:.0f}% share of his team's TDs and red-zone chances",
           f"{teams.info(p['team'])['name']} projected for {m.team_points(p['team'], p['opp'], p['team'] == m.home):.1f} points"]
    if p["injury"]:
        out.append(f"Listed {p['injury']['status']}")
    return out


def _player_summary(p):
    return {"id": p["id"], "name": p["name"], "team": p["team"], "pos": p["pos"], "role": p["role"],
            "rec_yds": round(p["rec_yds"], 1), "rec": round(p["rec"], 1), "rush_yds": round(p["rush_yds"], 1),
            "pass_yds": round(p["pass_yds"], 1), "pass_td": round(p["pass_td"], 2),
            "p_any": round(p.get("p_any", 0), 3), "p_first": round(p.get("p_first", 0), 3),
            "injury": (p["injury"] or {}).get("status")}
