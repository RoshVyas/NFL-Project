import { fmt } from "../format.js";
import { RankPill, seasonHeading } from "./Common.jsx";

export default function RoleTable({ roles, seasons, side, notes }) {
  const off = side === "off";
  return (
    <div className="scroll">
      <table className="stat-table role-table">
        <thead>
          <tr>
            <th rowSpan={2}>{off ? "Receiver spot" : "Against"}</th>
            {seasons.map((s) => (
              <th key={s} colSpan={3} className="num group">
                {seasonHeading(s, seasons, notes)}
              </th>
            ))}
          </tr>
          <tr>
            {seasons.map((s) => [
              <th key={`${s}a`} className="num">Tgt share</th>,
              <th key={`${s}b`} className="num">{off ? "Yds / g" : "Yds allowed / g"}</th>,
              <th key={`${s}c`} className="num">TD</th>,
            ])}
          </tr>
        </thead>
        <tbody>
          {roles.map((r) => (
            <tr key={r.role}>
              <td className="label">
                {r.label}
                {off && <PlayerNames players={r.players} seasons={seasons} />}
              </td>
              {seasons.map((s) => {
                const v = r.values[s] || {};
                return [
                  <td key={`${s}a`} className="num">
                    {fmt(v.tgt_share, "pct")}
                  </td>,
                  <td key={`${s}b`} className="num">
                    <span className="val">{fmt(v.yds_pg, "n1")}</span>
                    <RankPill rank={v.rank} better="high" />
                  </td>,
                  <td key={`${s}c`} className="num">
                    {fmt(v.td, "n0")}
                  </td>,
                ];
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PlayerNames({ players, seasons }) {
  const latest = seasons[seasons.length - 1];
  const list = players?.[latest] || [];
  if (!list.length) return null;
  return (
    <small>
      {list
        .slice(0, 2)
        .map((p) => p.name)
        .join(", ")}
    </small>
  );
}
