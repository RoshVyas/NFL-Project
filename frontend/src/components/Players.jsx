import { fmt } from "../format.js";
import { seasonHeading } from "./Common.jsx";

const ROLE_TAG = { X: "X", Z: "Z", SLOT: "Slot", WR: "WR", TE: "TE", RB: "RB" };

export function statLine(p, slot) {
  if (!p) return null;
  const parts = [];
  if (slot === "QB1" || (p.pass_att > 20 && p.pos === "QB")) {
    parts.push(`${p.pass_cmp}/${p.pass_att}`, `${p.pass_yds} yds`, `${p.pass_td} TD`, `${p.ints} INT`);
    if (p.carries) parts.push(`${p.rush_yds} rush yds`);
    return parts.join(" · ");
  }
  if (slot?.startsWith("RB") || (p.carries > p.targets && p.carries > 0)) {
    parts.push(`${p.carries} car`, `${p.rush_yds} yds`, `${p.rush_td} TD`);
    if (p.targets) parts.push(`${p.rec} rec, ${p.rec_yds} yds`);
    return parts.join(" · ");
  }
  parts.push(`${p.targets} tgt`, `${p.rec} rec`, `${p.rec_yds} yds`, `${p.rec_td} TD`);
  if (p.adot != null) parts.push(`aDOT ${p.adot}`);
  return parts.join(" · ");
}

export function KeyPlayers({ players, seasons, team, notes }) {
  if (!players?.length) return <p className="muted">No depth chart available.</p>;
  return (
    <div className="key-players">
      {players.map((p) => (
        <div key={p.slot} className="kp">
          <div className="kp-head">
            <span className="kp-role">{p.label}</span>
            {p.deep_threat && <span className="tag deep">Deep threat</span>}
          </div>
          <div className="kp-name">{p.name}</div>
          {seasons.map((s) => {
            const line = p.seasons?.[s];
            const other = line?.teams && !line.teams.includes(team);
            return (
              <div key={s} className="kp-line">
                <span className="kp-season">{seasonHeading(s, seasons, notes)}</span>
                {line ? (
                  <span>
                    {statLine(line, p.slot)}
                    {other && <em> (with {line.teams.join("/")})</em>}
                  </span>
                ) : (
                  <span className="muted">No stats</span>
                )}
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}

const COLUMNS = {
  targets: [
    ["Tgt", (p) => p.targets],
    ["Share", (p) => fmt(p.tgt_share, "pct")],
    ["Yds", (p) => p.rec_yds],
    ["TD", (p) => p.rec_td],
  ],
  td: [
    ["Rec TD", (p) => p.rec_td],
    ["Rush TD", (p) => p.rush_td],
    ["Total", (p) => p.total_td],
  ],
  rushers: [
    ["Car", (p) => p.carries],
    ["Yds", (p) => p.rush_yds],
    ["YPC", (p) => (p.carries ? (p.rush_yds / p.carries).toFixed(1) : "–")],
    ["TD", (p) => p.rush_td],
  ],
  rz: [
    ["RZ tgt", (p) => p.rz_tgts],
    ["RZ car", (p) => p.rz_carries],
    ["TD", (p) => p.total_td],
  ],
  deep: [
    ["Deep tgt", (p) => p.deep_tgts],
    ["aDOT", (p) => fmt(p.adot, "n1")],
    ["Yds", (p) => p.rec_yds],
  ],
};

export function LeaderTable({ leaders, kind, seasons, limit = 6, notes }) {
  const cols = COLUMNS[kind];
  return (
    <div className={`season-cols n${seasons.length}`}>
      {seasons.map((s) => {
        const rows = (leaders?.[s]?.[kind] || []).slice(0, limit);
        return (
          <div key={s} className="season-col">
            <div className="season-label">{seasonHeading(s, seasons, notes)}</div>
            {rows.length === 0 ? (
              <p className="muted">None yet.</p>
            ) : (
              <table className="leader-table">
                <thead>
                  <tr>
                    <th>Player</th>
                    {cols.map(([h]) => (
                      <th key={h} className="num">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((p) => (
                    <tr key={p.id}>
                      <td className="label">
                        {p.name}
                        <span className="tag">{ROLE_TAG[p.role] || p.pos}</span>
                      </td>
                      {cols.map(([h, get]) => (
                        <td key={h} className="num">
                          {get(p)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        );
      })}
    </div>
  );
}
