import { fmt } from "../format.js";
import { RankPill, seasonHeading } from "./Common.jsx";

function change(row, a, b) {
  const va = row.values[a];
  const vb = row.values[b];
  if (!va || !vb || va.v == null || vb.v == null) return <span className="trend flat">–</span>;
  if (row.better && va.rank && vb.rank) {
    const d = va.rank - vb.rank; // positive = rank number went down = improved
    if (d >= 4) return <span className="trend up">Better</span>;
    if (d <= -4) return <span className="trend down">Worse</span>;
    return <span className="trend flat">Steady</span>;
  }
  const diff = vb.v - va.v;
  if (Math.abs(diff) < 0.05) return <span className="trend flat">Steady</span>;
  return (
    <span className="trend flat">
      {diff > 0 ? "▲" : "▼"} {fmt(Math.abs(diff), row.fmt === "pct" ? "n1" : row.fmt)}
    </span>
  );
}

export default function StatTable({ rows, seasons, notes }) {
  const showChange = seasons.length === 2;
  return (
    <div className="scroll">
      <table className="stat-table">
        <thead>
          <tr>
            <th>Stat</th>
            {seasons.map((s) => (
              <th key={s} className="num">
                {seasonHeading(s, seasons, notes)}
              </th>
            ))}
            {showChange && <th className="num">Change</th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.key}>
              <td className="label">
                {row.label}
                {row.sub && <small>{row.sub}</small>}
              </td>
              {seasons.map((s) => {
                const val = row.values[s];
                return (
                  <td key={s} className="num">
                    <span className="val">{fmt(val?.v, row.fmt)}</span>
                    <RankPill rank={val?.rank} better={row.better} />
                  </td>
                );
              })}
              {showChange && <td className="num">{change(row, seasons[0], seasons[1])}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
