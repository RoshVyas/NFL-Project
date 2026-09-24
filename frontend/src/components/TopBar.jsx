import { useMemo, useState } from "react";
import { formatGameTime } from "../format.js";

export default function TopBar({ games, teams, selection, onSelect, view, seasons, onView, onRefresh, loading, generatedAt }) {
  const [custom, setCustom] = useState({ away: "GB", home: "CHI" });

  const byDay = useMemo(() => {
    const groups = new Map();
    for (const g of games) {
      const label = new Date(`${g.gameday}T12:00:00`).toLocaleDateString(undefined, {
        weekday: "long",
        month: "short",
        day: "numeric",
      });
      if (!groups.has(label)) groups.set(label, []);
      groups.get(label).push(g);
    }
    return [...groups.entries()];
  }, [games]);

  const value = selection?.type === "game" ? selection.id : "__custom";

  const onGameChange = (e) => {
    if (e.target.value === "__custom") onSelect({ type: "teams", ...custom });
    else onSelect({ type: "game", id: e.target.value });
  };

  const setCustomTeam = (side, abbr) => {
    const next = { ...custom, [side]: abbr };
    setCustom(next);
    if (next.away !== next.home) onSelect({ type: "teams", ...next });
  };

  return (
    <header className="topbar">
      <div className="brand">
        Matchup<span>Board</span>
      </div>
      <div className="controls">
        <label className="field">
          <span>Game</span>
          <select value={value} onChange={onGameChange}>
            {byDay.map(([day, gs]) => (
              <optgroup key={day} label={day}>
                {gs.map((g) => (
                  <option key={g.game_id} value={g.game_id}>
                    {g.away} @ {g.home} · {formatGameTime(g).split(" · ")[1] || g.gameday}
                  </option>
                ))}
              </optgroup>
            ))}
            <option value="__custom">Pick any two teams…</option>
          </select>
        </label>

        {selection?.type === "teams" && (
          <div className="custom-pick">
            <select aria-label="Away team" value={custom.away} onChange={(e) => setCustomTeam("away", e.target.value)}>
              {teams.map((t) => (
                <option key={t.abbr} value={t.abbr}>
                  {t.full_name}
                </option>
              ))}
            </select>
            <span>@</span>
            <select aria-label="Home team" value={custom.home} onChange={(e) => setCustomTeam("home", e.target.value)}>
              {teams.map((t) => (
                <option key={t.abbr} value={t.abbr}>
                  {t.full_name}
                </option>
              ))}
            </select>
          </div>
        )}

        <div className="field">
          <span>Seasons</span>
          <div className="seg" role="group" aria-label="Seasons shown">
            {seasons.length > 1 && (
              <button aria-pressed={view === "both"} onClick={() => onView("both")}>
                {seasons.join(" vs ")}
              </button>
            )}
            {seasons.map((s) => (
              <button key={s} aria-pressed={view === s} onClick={() => onView(s)}>
                {s} only
              </button>
            ))}
          </div>
        </div>

        <button className="btn" onClick={onRefresh} disabled={loading} title="Download the newest data from nflverse">
          {loading ? "Loading…" : "Refresh data"}
        </button>
        {generatedAt && (
          <span className="updated">
            Updated {new Date(generatedAt).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}
          </span>
        )}
      </div>
    </header>
  );
}
