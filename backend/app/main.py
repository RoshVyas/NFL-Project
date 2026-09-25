"""HTTP API for the matchup dashboard.

Run from the backend folder:  uvicorn app.main:app --reload --port 8000
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import config, report, sources, teams
from . import roles as roles_mod

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="NFL Matchup Board")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    prior, cur = config.seasons()
    return {"ok": True, "seasons": [prior, cur]}


@app.get("/api/teams")
def list_teams():
    return teams.all_teams()


@app.get("/api/games")
def games(days: int = Query(7, ge=1, le=30)):
    try:
        return {"games": report.upcoming_games(days)}
    except sources.DataUnavailable as exc:
        raise HTTPException(503, str(exc))


@app.get("/api/matchup/{game_id}")
def matchup_by_game(game_id: str):
    try:
        game = report.find_game(game_id)
        if not game:
            raise HTTPException(404, f"No game with id {game_id}")
        return report.matchup(game["away"], game["home"], game)
    except sources.DataUnavailable as exc:
        raise HTTPException(503, str(exc))


@app.get("/api/matchup")
def matchup_by_teams(away: str, home: str):
    if not teams.is_team(away) or not teams.is_team(home):
        raise HTTPException(400, "Unknown team abbreviation")
    if teams.normalize(away) == teams.normalize(home):
        raise HTTPException(400, "Pick two different teams")
    try:
        return report.matchup(away, home, None)
    except sources.DataUnavailable as exc:
        raise HTTPException(503, str(exc))


@app.get("/api/rankings")
def rankings(season: Optional[int] = None, side: str = Query("def", pattern="^(off|def)$")):
    prior, cur = config.seasons()
    season = season or cur
    if season not in (prior, cur):
        raise HTTPException(400, f"Season must be {prior} or {cur}")
    try:
        return report.league_rankings(season, side)
    except sources.DataUnavailable as exc:
        raise HTTPException(503, str(exc))


class RoleUpdate(BaseModel):
    season: int
    X: Optional[str] = None
    Z: Optional[str] = None
    SLOT: Optional[str] = None


@app.put("/api/roles/{team}")
def set_roles(team: str, body: RoleUpdate):
    if not teams.is_team(team):
        raise HTTPException(400, "Unknown team abbreviation")
    roles_mod.save_override(body.season, teams.normalize(team), {"X": body.X, "Z": body.Z, "SLOT": body.SLOT})
    report.clear_cache()
    return {"ok": True}


@app.delete("/api/roles/{team}")
def reset_roles(team: str, season: int):
    roles_mod.save_override(season, teams.normalize(team), {})
    report.clear_cache()
    return {"ok": True}


@app.post("/api/refresh")
def refresh():
    """Pull the newest current-season files from nflverse right now."""
    sources.force_refresh()
    report.clear_cache()
    return {"ok": True}


# Serve the built React app when it exists (npm run build), so one server runs everything.
if config.FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=config.FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        return FileResponse(config.FRONTEND_DIST / "index.html")
