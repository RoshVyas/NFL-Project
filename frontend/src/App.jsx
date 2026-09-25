import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "./api.js";
import TopBar from "./components/TopBar.jsx";
import MatchupHeader from "./components/MatchupHeader.jsx";
import EdgeBoard from "./components/EdgeBoard.jsx";
import TeamHalf from "./components/TeamHalf.jsx";
import Rankings from "./components/Rankings.jsx";

const VIEW_KEY = "matchup-board:view";

function loadView() {
  try {
    return localStorage.getItem(VIEW_KEY) || "both";
  } catch {
    return "both";
  }
}

export default function App() {
  const [games, setGames] = useState([]);
  const [teams, setTeams] = useState([]);
  const [selection, setSelection] = useState(null);
  const [view, setView] = useState(loadView);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [tabs, setTabs] = useState({ away: "offense", home: "defense" });
  const [reloadKey, setReloadKey] = useState(0);
  const [page, setPage] = useState("matchup");

  useEffect(() => {
    api
      .games()
      .then((res) => {
        setGames(res.games);
        if (res.games.length) setSelection({ type: "game", id: res.games[0].game_id });
      })
      .catch((e) => setError(e.message));
    api.teams().then(setTeams).catch(() => {});
  }, []);

  useEffect(() => {
    if (!selection) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    const req =
      selection.type === "game"
        ? api.matchupByGame(selection.id)
        : api.matchupByTeams(selection.away, selection.home);
    req
      .then((res) => !cancelled && setData(res))
      .catch((e) => !cancelled && setError(e.message))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [selection, reloadKey]);

  const changeView = (v) => {
    setView(v);
    try {
      localStorage.setItem(VIEW_KEY, v);
    } catch {
      /* private mode */
    }
  };

  const shownSeasons = useMemo(() => {
    if (!data) return [];
    const all = data.seasons.map(String);
    return view === "both" ? all : all.filter((s) => s === view);
  }, [data, view]);

  const reload = useCallback(() => setReloadKey((k) => k + 1), []);

  const refreshData = async () => {
    setLoading(true);
    try {
      await api.refresh();
      const res = await api.games();
      setGames(res.games);
      reload();
    } catch (e) {
      setError(e.message);
      setLoading(false);
    }
  };

  const away = data?.away?.team?.abbr;
  const home = data?.home?.team?.abbr;
  const presets = data
    ? [
        { label: `${away} offense vs ${home} defense`, tabs: { away: "offense", home: "defense" } },
        { label: `${home} offense vs ${away} defense`, tabs: { away: "defense", home: "offense" } },
        { label: "Both offenses", tabs: { away: "offense", home: "offense" } },
        { label: "Both defenses", tabs: { away: "defense", home: "defense" } },
        { label: "Depth charts", tabs: { away: "depth", home: "depth" } },
      ]
    : [];

  return (
    <div className="app">
      <nav className="page-nav" aria-label="Pages">
        <button aria-current={page === "matchup" ? "page" : undefined} onClick={() => setPage("matchup")}>
          Matchup
        </button>
        <button aria-current={page === "rankings" ? "page" : undefined} onClick={() => setPage("rankings")}>
          League rankings
        </button>
      </nav>

      <TopBar
        games={games}
        teams={teams}
        selection={selection}
        onSelect={setSelection}
        view={view}
        seasons={data?.seasons?.map(String) ?? []}
        onView={changeView}
        onRefresh={refreshData}
        loading={loading}
        generatedAt={data?.generated_at}
      />

      {error && (
        <div className="notice error" role="alert">
          <strong>Couldn't load the data.</strong> {error}. Check that the Python server is running on port 8000,
          then <button className="link" onClick={reload}>try again</button>.
        </div>
      )}

      {!data && loading && (
        <div className="loading-screen">
          <div className="spinner" aria-hidden="true" />
          <p>Loading play-by-play data. The first run downloads about 100 MB of NFL data, so it can take a minute.</p>
        </div>
      )}

      {page === "rankings" && data && (
        <Rankings seasons={data.seasons.map(String)} />
      )}

      {page === "matchup" && data && (
        <main className={loading ? "is-loading" : ""}>
          <MatchupHeader data={data} />
          <SeasonNotes notes={data.season_notes} />
          <EdgeBoard data={data} seasons={shownSeasons} />

          <div className="preset-bar" role="group" aria-label="Quick views">
            {presets.map((p) => {
              const active = p.tabs.away === tabs.away && p.tabs.home === tabs.home;
              return (
                <button key={p.label} className={active ? "active" : ""} onClick={() => setTabs(p.tabs)}>
                  {p.label}
                </button>
              );
            })}
          </div>

          <div className="halves">
            <TeamHalf
              report={data.away}
              opponent={data.home}
              side="away"
              tab={tabs.away}
              onTab={(t) => setTabs((s) => ({ ...s, away: t }))}
              seasons={shownSeasons}
              notes={data.season_notes}
              onRolesSaved={reload}
            />
            <TeamHalf
              report={data.home}
              opponent={data.away}
              side="home"
              tab={tabs.home}
              onTab={(t) => setTabs((s) => ({ ...s, home: t }))}
              seasons={shownSeasons}
              notes={data.season_notes}
              onRolesSaved={reload}
            />
          </div>

          <footer className="footer">
            <p>
              Data: <a href="https://github.com/nflverse" target="_blank" rel="noreferrer">nflverse</a> play-by-play,
              FTN charting, participation data and daily ESPN depth charts. Regular season only. Ranks run 1–32 where 1
              is best for that unit. Numbers for {data.seasons[data.seasons.length - 1]} cover the games played so far.
            </p>
            <p>
              X, Z and slot roles are assigned per team from the depth chart and each receiver's average target depth
              (the shortest is treated as the slot). Fix any team's roles in its Depth chart tab.
            </p>
          </footer>
        </main>
      )}
    </div>
  );
}

function SeasonNotes({ notes }) {
  const msgs = [];
  for (const [season, n] of Object.entries(notes)) {
    if (!n.available) msgs.push(`${season}: no games played yet.`);
    else if (!n.has_coverage)
      msgs.push(
        `${season}: man/zone and coverage-shell charting is published by nflverse after the season, so those rows only show ${
          Number(season) - 1
        } for now. Blitz, play action and everything else is live through week ${n.last_week}.`
      );
  }
  if (!msgs.length) return null;
  return <div className="notice">{msgs.join(" ")}</div>;
}
