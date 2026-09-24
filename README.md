# Matchup Board

Pick any NFL game in the next 7 days and see both teams side by side: each offense, each defense, the full depth
chart, and a mismatch finder that lines up one team's offensive strengths against the other team's defensive weak
spots. Last season and this season are shown next to each other, never blended.

- **Backend:** Python + FastAPI + pandas (`backend/`)
- **Frontend:** React + Vite (`frontend/`)
- **Data:** [nflverse](https://github.com/nflverse), free and updated through the season. No API keys needed.

## Run it on your Mac

You need **Python 3.10+** and **Node 18+**. If you don't have them, install [Homebrew](https://brew.sh), then:

```bash
brew install python node
```

Then, in the project folder:

```bash
./setup.sh   # once: creates backend/.venv and installs Python + npm packages
./dev.sh     # every time: starts the API and the website, then opens http://localhost:5173
```

The first page load downloads about 100 MB of play-by-play data into `backend/cache/`, so give it a minute. After
that it loads in about a second.

### In VS Code

1. Open the project folder (`File → Open Folder…`). Install the recommended extensions when prompted.
2. Run the setup once: `Terminal → Run Task… → Setup (install everything)`.
3. Start the app: `Terminal → Run Build Task…` (⇧⌘B) runs **Start app**, which starts both servers.
4. Open http://localhost:5173.

To debug the Python side, use the **Debug API (FastAPI)** launch config in the Run and Debug panel (stop the
normal backend task first so port 8000 is free). Tests: `Terminal → Run Task… → Backend: run tests`.

## What's on the screen

**Top:** game picker (every game in the next 7 days, or "Pick any two teams"), a season switch (`2025 vs 2026`,
`2025 only`, `2026 only`), and **Refresh data**, which pulls the newest files from nflverse right away.

**Mismatches:** two lists, one per offense. Each row is an area (X, Z or slot receiver, tight end, RB rushing and
receiving, QB rushing, deep passing, big plays, red zone, efficiency, 3rd downs, protection). It shows the offense's
rank, the defense's rank, the player who fills that spot and a verdict: **Big edge / Edge / Even / Tough**.

**Two halves:** the away team on the left and the home team on the right. Each half has its own tabs, and the quick
buttons (for example "ATL offense vs GB defense") set both halves at once.

| Offense tab | Defense tab |
| --- | --- |
| At a glance: pass-first or run-first, play action, the most productive receiver spot | At a glance: man or zone, favourite coverage, blitz habits, weak spots |
| Key players: QB, RB1/RB2, X, Z, slot, TE1/TE2 with each season's stat line | Coverage: man %, zone %, blitz %, pass rushers, pressure, sacks, coverage shells (Cover 0/1/2/3/4/6) |
| Who they target: target share leaders with their receiver spot | Yards allowed by receiver spot: X, Z, slot, other WRs, TE, RB |
| Production by receiver spot: target share, yards/game and TDs for X, Z, slot, TE, RB | Touchdowns allowed: the top 3 positions that score on them |
| Who scores the TDs: top 3 positions, then the players | Yards and points allowed, EPA, success rate, 3rd downs |
| Identity: pass/run rate (overall and neutral situations), plays, points, play action, screens, motion | Run defense: RB and QB rush yards allowed, yards per carry by run direction |
| Production, run game (with run direction), deep passing, red zone, protection | Deep passes, red zone, results against man vs zone |

**Depth chart tab:** the latest ESPN depth chart for offense, defense and special teams, with X / Z / slot and deep
threat tags. This is also where you edit receiver roles (see below).

Every stat shows its **rank out of 32**. 1 is always best *for that unit*, so on a defense 32 means it gives up the
most. Green means top 8, red means bottom 8, and blue-grey means a tendency that isn't good or bad (like pass rate).

## Where the data comes from

| What | Source | Updated |
| --- | --- | --- |
| Play-by-play (yards, targets, air yards, run direction, red zone, EPA) | nflverse `pbp` | after each game day |
| Blitzers, pass rushers, play action, screens, motion | nflverse `ftn_charting` | weekly |
| Man/zone, coverage shells, pressure | nflverse `pbp_participation` | after the season ends |
| Depth charts and player names | nflverse `depth_charts` (daily ESPN snapshots) | daily |
| Schedule, betting lines | nflverse `nfldata/games.csv` | daily |

Files are cached in `backend/cache/`. Current-season files are re-downloaded when they're more than 3 hours old
(6 hours for depth charts). Last season's files are refreshed weekly. If you're offline, the app uses the cached
copies. Stats use regular-season games only.

**Coverage for the current season:** nflverse publishes man/zone and coverage-shell charting only after a season
ends. Until then those rows show last season's numbers and "–" for the current season. Blitz rate, pass rushers and
play action come from FTN charting, which is live during the season.

## How X, Z and slot are decided

No free data source says where a receiver lines up on every snap, so the app assigns roles per team and season:

1. Take the three starting WRs: the top three on the latest depth chart (current season) or the three most-targeted
   WRs (past seasons).
2. The one with the shortest average depth of target (aDOT) is the **slot**.
3. Of the other two, the higher on the depth chart (or in targets) is **X**, the other is **Z**.
4. The starter with the deepest aDOT (12+ yards) is tagged **deep threat**.

This is right most of the time but not always. If you know better, open a team's **Depth chart** tab, choose
**Edit roles**, pick the players and save. Your choices are stored in `backend/user_data/role_overrides.json`, and
every by-receiver-spot stat, mismatch and TD split is recalculated with them. Other WRs are grouped as "Other WRs".

## Project layout

```
backend/
  app/
    main.py      FastAPI routes (also serves the built React app)
    sources.py   downloads and caches the nflverse files
    stats.py     turns play-by-play into offense and defense profiles for all 32 teams
    metrics.py   stat labels, formats, which direction is good, mismatch definitions
    roles.py     X / Z / slot assignment and manual overrides
    report.py    builds a full matchup: both teams, depth charts, mismatches
    teams.py     team names, colors and logos
  tests/         pytest unit tests
frontend/
  src/
    App.jsx      page layout and state
    components/  top bar, mismatch board, team halves, tables, charts, depth chart
setup.sh / dev.sh
```

### API

| Endpoint | What it returns |
| --- | --- |
| `GET /api/games?days=7` | upcoming games |
| `GET /api/matchup/{game_id}` | everything for one game, for example `2026_03_ATL_GB` |
| `GET /api/matchup?away=ATL&home=GB` | the same for any two teams |
| `PUT /api/roles/{team}` | save X/Z/slot picks: `{"season": 2026, "X": "<gsis id>", "Z": "...", "SLOT": "..."}` |
| `DELETE /api/roles/{team}?season=2026` | go back to automatic roles |
| `POST /api/refresh` | re-download the current season's files |

## Running as a single server

```bash
cd frontend && npm run build && cd ..
backend/.venv/bin/uvicorn app.main:app --app-dir backend --port 8000
```

Then open http://localhost:8000. FastAPI serves the built site and the API together.

## Troubleshooting

- **"Couldn't load the data"**: make sure the backend is running (`./dev.sh` starts it) and you're online for the
  first download.
- **Numbers look stale**: click **Refresh data**. nflverse usually posts play-by-play within a few hours of games
  finishing.
- **Start from scratch**: delete `backend/cache/` and reload the page.
