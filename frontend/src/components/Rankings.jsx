import { useEffect, useMemo, useState } from "react";
import { api } from "../api.js";
import { fmt } from "../format.js";
import { RankPill } from "./Common.jsx";
import TeamLogo from "./TeamLogo.jsx";

export default function Rankings({ seasons, highlight }) {
  const [season, setSeason] = useState(seasons[seasons.length - 1]);
  const [side, setSide] = useState("def");
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [sort, setSort] = useState({ key: "ALLRB_rush_yds_pg", byRank: true });

  useEffect(() => {
    if (!season) return;
    setError(null);
    api
      .rankings(season, side)
      .then(setData)
      .catch((e) => setError(e.message));
  }, [season, side]);

  const rows = useMemo(() => {
    if (!data?.teams) return [];
    const r = [...data.teams];
    if (sort.key === "team") return r.sort((a, b) => a.team.name.localeCompare(b.team.name));
    return r.sort((a, b) => (a.values[sort.key]?.rank ?? 99) - (b.values[sort.key]?.rank ?? 99));
  }, [data, sort]);

  const sortCol = data?.columns.find((c) => c.key === sort.key);
  const defense = side === "def";

  return (
    <section className="rankings" aria-label="League rankings">
      <div className="section-head">
        <h2>League rankings</h2>
        <p>
          All 32 {defense ? "defenses" : "offenses"} ranked per game.{" "}
          {defense
            ? "1 gives up the fewest yards, 32 the most."
            : "1 produces the most yards, 32 the fewest."}{" "}
          Click a column to sort by it.
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
        {sortCol && (
          <span className="muted small">
            Sorted by <strong>{sortCol.label}</strong>: {sortCol.desc.toLowerCase()}
            {defense ? " allowed" : ""}.
          </span>
        )}
      </div>

      {error && <div className="notice error">Couldn't load rankings: {error}</div>}

      {data && (
        <div className="card">
          <div className="scroll">
            <table className="stat-table rank-table">
              <thead>
                <tr>
                  <th className="num">#</th>
                  <th>
                    <button className="th-btn" onClick={() => setSort({ key: "team" })}>Team</button>
                  </th>
                  {data.columns.map((c) => (
                    <th key={c.key} className={`num ${sort.key === c.key ? "sorted" : ""}`} title={c.desc}>
                      <button className="th-btn" onClick={() => setSort({ key: c.key })}>
                        {c.label}
                        {sort.key === c.key ? " ▲" : ""}
                      </button>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((t, i) => (
                  <tr key={t.team.abbr} className={highlight?.includes(t.team.abbr) ? "hl" : ""}>
                    <td className="num muted">{sort.key === "team" ? "" : t.values[sort.key]?.rank ?? i + 1}</td>
                    <td className="team-cell">
                      <TeamLogo team={t.team} size={22} />
                      <span>
                        {t.team.name}
                        <small className="muted"> {t.record}</small>
                      </span>
                    </td>
                    {data.columns.map((c) => {
                      const v = t.values[c.key];
                      return (
                        <td key={c.key} className={`num ${sort.key === c.key ? "sorted" : ""}`}>
                          <span className="val">{fmt(v?.v, c.fmt)}</span>
                          <RankPill rank={v?.rank} better={c.better} />
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
        RB columns include every running back. Teams in the game you have open are highlighted.
      </p>
    </section>
  );
}
