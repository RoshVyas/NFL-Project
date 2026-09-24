import { useEffect, useMemo, useState } from "react";
import { api } from "../api.js";
import { fmt } from "../format.js";

export default function Rankings({ seasons }) {
  const [season, setSeason] = useState(seasons[seasons.length - 1]);
  const [side, setSide] = useState("def");
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [focus, setFocus] = useState([]);

  useEffect(() => {
    if (!season) return;
    setError(null);
    api
      .rankings(season, side)
      .then(setData)
      .catch((e) => setError(e.message));
  }, [season, side]);

  // Each column is its own 1-32 list. Tied teams share a rank ("=8") and are listed A-Z.
  const columns = useMemo(() => {
    if (!data?.teams) return [];
    return data.columns.map((c) => {
      const entries = data.teams
        .map((t) => ({ team: t.team, v: t.values[c.key]?.v, rank: t.values[c.key]?.rank }))
        .sort((a, b) => (a.rank ?? 99) - (b.rank ?? 99) || a.team.name.localeCompare(b.team.name));
      const counts = {};
      for (const e of entries) if (e.rank) counts[e.rank] = (counts[e.rank] || 0) + 1;
      return { ...c, entries: entries.map((e) => ({ ...e, tied: counts[e.rank] > 1 })) };
    });
  }, [data]);

  const toggleFocus = (abbr) =>
    setFocus((f) => (f.includes(abbr) ? f.filter((x) => x !== abbr) : [...f, abbr]));

  const defense = side === "def";
  const rowCount = columns[0]?.entries.length ?? 0;

  return (
    <section className="rankings" aria-label="League rankings">
      <div className="section-head">
        <h2>League rankings</h2>
        <p>
          Every column is its own 1–32 list, per game.{" "}
          {defense ? "1 gives up the fewest, 32 the most." : "1 produces the most, 32 the fewest."} "=8" means tied
          for 8th. Click a team to pick it out in every column.
        </p>
      </div>

      <div className="rank-controls">
        <div className="seg" role="group" aria-label="Unit">
          <button aria-pressed={defense} onClick={() => setSide("def")}>Defenses (allowed)</button>
          <button aria-pressed={!defense} onClick={() => setSide("off")}>Offenses (produced)</button>
        </div>
        <div className="seg" role="group" aria-label="Season">
          {seasons.map((s) => (
            <button key={s} aria-pressed={season === s} onClick={() => setSeason(s)}>
              {s}
              {data?.season === Number(s) && data.last_week < 18 ? ` (wk 1–${data.last_week})` : ""}
            </button>
          ))}
        </div>
        {focus.length > 0 && (
          <button className="link small" onClick={() => setFocus([])}>
            Clear picked teams
          </button>
        )}
      </div>

      {error && <div className="notice error">Couldn't load rankings: {error}</div>}

      {data && (
        <div className="card">
          <div className="scroll">
            <table className="rank-board">
              <thead>
                <tr>
                  {columns.map((c) => (
                    <th key={c.key} title={`${c.desc}${defense ? " allowed" : ""}`}>
                      {c.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {Array.from({ length: rowCount }, (_, i) => (
                  <tr key={i}>
                    {columns.map((c) => {
                      const e = c.entries[i];
                      const picked = focus.includes(e.team.abbr);
                      return (
                        <td key={c.key} className={picked ? "picked" : ""}>
                          <button
                            className="rb-cell"
                            onClick={() => toggleFocus(e.team.abbr)}
                            title={`${e.team.full_name}: ${fmt(e.v, c.fmt)}`}
                          >
                            <span className="rb-rank">{e.rank ? `${e.tied ? "=" : ""}${e.rank}` : "–"}</span>
                            <span className="rb-team">{e.team.abbr}</span>
                            <span className="rb-val">{fmt(e.v, c.fmt)}</span>
                          </button>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      <p className="muted small">
        X, Z and slot use each team's receiver roles (see a team's Depth chart tab). TE is the "Y" in most playbooks.
        RB columns include every running back.
      </p>
    </section>
  );
}
