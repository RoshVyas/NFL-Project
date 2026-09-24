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

  // How many teams share each rank, per column, so ties can be labelled "T8".
  const tieCounts = useMemo(() => {
    const out = {};
    for (const c of data?.columns ?? []) {
      const counts = {};
      for (const t of data.teams) {
        const rk = t.values[c.key]?.rank;
        if (rk) counts[rk] = (counts[rk] || 0) + 1;
      }
      out[c.key] = counts;
    }
    return out;
  }, [data]);

  // Sorted 1-32; tied teams are grouped and listed alphabetically, since their order means nothing.
  const groups = useMemo(() => {
    if (!data?.teams) return [];
    const byName = (a, b) => a.team.name.localeCompare(b.team.name);
    if (sort.key === "team") return [...data.teams].sort(byName).map((t) => ({ rank: null, teams: [t] }));
    const rankOf = (t) => t.values[sort.key]?.rank ?? 99;
    const sorted = [...data.teams].sort((a, b) => rankOf(a) - rankOf(b) || byName(a, b));
    const out = [];
    for (const t of sorted) {
      const last = out[out.length - 1];
      if (last && last.rank === rankOf(t)) last.teams.push(t);
      else out.push({ rank: rankOf(t), teams: [t] });
    }
    return out;
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
                {groups.map((g, gi) =>
                  g.teams.map((t, i) => {
                    const tied = g.teams.length > 1;
                    const classes = [
                      highlight?.includes(t.team.abbr) ? "hl" : "",
                      tied ? "tie" : "",
                      tied && i === 0 ? "tie-first" : "",
                      tied && i === g.teams.length - 1 ? "tie-last" : "",
                      gi % 2 ? "band" : "",
                    ].join(" ");
                    return (
                      <tr key={t.team.abbr} className={classes}>
                        {i === 0 && (
                          <td className="num rank-cell" rowSpan={g.teams.length}>
                            {g.rank == null || g.rank === 99 ? (
                              "–"
                            ) : tied ? (
                              <>
                                <strong>T-{g.rank}</strong>
                                <small>{g.teams.length} tied</small>
                              </>
                            ) : (
                              <strong>{g.rank}</strong>
                            )}
                          </td>
                        )}
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
                              <RankPill rank={v?.rank} better={c.better} tiedWith={tieCounts[c.key]?.[v?.rank] || 0} />
                            </td>
                          );
                        })}
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
      <p className="muted small">
        X, Z and slot use each team's receiver roles (see a team's Depth chart tab). TE is the "Y" in most playbooks.
        RB columns include every running back. Teams in the game you have open are highlighted. "T-8" means tied
        for 8th: tied teams share a rank and are listed alphabetically.
      </p>
    </section>
  );
}
