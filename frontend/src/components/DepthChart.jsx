import { useMemo, useState } from "react";
import { api } from "../api.js";
import { Card } from "./Common.jsx";

const ROLE_TAG = { X: "X", Z: "Z", SLOT: "Slot" };

export default function DepthChart({ report, seasons, onRolesSaved }) {
  const dc = report.depth_chart;
  return (
    <>
      <RoleEditor report={report} seasons={seasons} onSaved={onRolesSaved} />
      {dc.groups.length === 0 && (
        <Card title="Depth chart">
          <p className="muted">No depth chart published for this team yet.</p>
        </Card>
      )}
      {dc.groups.map((g) => (
        <Card
          key={g.title}
          title={g.title}
          desc={g.title === "Offense" ? "Base formation: 3 WR, 1 TE" : g.formation}
          aside={dc.updated && <span className="muted small">As of {new Date(dc.updated).toLocaleDateString()}</span>}
        >
          <DepthTable positions={g.positions} />
        </Card>
      ))}
    </>
  );
}

function DepthTable({ positions }) {
  const cols = Math.min(4, Math.max(...positions.map((p) => p.players.length)));
  return (
    <div className="scroll">
      <table className="depth-table">
        <thead>
          <tr>
            <th>Pos</th>
            <th>Starter</th>
            {Array.from({ length: cols - 1 }, (_, i) => (
              <th key={i}>{["2nd", "3rd", "4th"][i]}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {positions.map((p) => (
            <tr key={p.pos + p.pos_name}>
              <td className="pos" title={p.pos_name}>
                {p.pos}
              </td>
              {Array.from({ length: cols }, (_, i) => {
                const pl = p.players[i];
                return (
                  <td key={i} className={i === 0 ? "starter" : ""}>
                    {pl ? (
                      <>
                        {pl.name}
                        {pl.role && <span className={`tag role-${pl.role}`}>{ROLE_TAG[pl.role]}</span>}
                        {pl.deep_threat && <span className="tag deep">Deep</span>}
                      </>
                    ) : null}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RoleEditor({ report, seasons, onSaved }) {
  const available = seasons.filter((s) => report.role_info[s]);
  const [season, setSeason] = useState(available[available.length - 1]);
  const info = report.role_info[season] || report.role_info[available[available.length - 1]];
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState({});
  const [status, setStatus] = useState(null);

  const depthWrs = useMemo(() => {
    const off = report.depth_chart.groups.find((g) => g.title === "Offense");
    if (!off) return [];
    return off.positions
      .filter((p) => p.pos.startsWith("WR"))
      .flatMap((p) => p.players)
      .filter((p) => p.id);
  }, [report]);

  if (!info) return null;
  const activeSeason = report.role_info[season] ? season : available[available.length - 1];
  const isCurrent = activeSeason === available[available.length - 1];

  const options = [...info.options];
  if (isCurrent) {
    for (const p of depthWrs) {
      if (!options.some((o) => o.id === p.id)) options.push({ id: p.id, name: p.name, targets: 0, adot: null });
    }
  }

  const start = () => {
    setDraft({
      X: info.starters.X?.id || "",
      Z: info.starters.Z?.id || "",
      SLOT: info.starters.SLOT?.id || "",
    });
    setEditing(true);
    setStatus(null);
  };

  const save = async () => {
    setStatus("Saving…");
    try {
      await api.saveRoles(report.team.abbr, Number(activeSeason), draft);
      setEditing(false);
      setStatus("Saved. Stats are being recalculated.");
      onSaved();
    } catch (e) {
      setStatus(`Couldn't save: ${e.message}`);
    }
  };

  const reset = async () => {
    setStatus("Resetting…");
    try {
      await api.resetRoles(report.team.abbr, Number(activeSeason));
      setEditing(false);
      setStatus("Back to automatic roles.");
      onSaved();
    } catch (e) {
      setStatus(`Couldn't reset: ${e.message}`);
    }
  };

  return (
    <Card
      title="Receiver roles"
      desc={`How ${report.team.name} receivers are split into X, Z and slot. Every "by receiver spot" stat uses this.`}
      aside={
        available.length > 1 && (
          <div className="seg small" role="group" aria-label="Season">
            {available.map((s) => (
              <button key={s} aria-pressed={activeSeason === s} onClick={() => { setSeason(s); setEditing(false); }}>
                {s}
              </button>
            ))}
          </div>
        )
      }
    >
      <div className="roles-grid">
        {["X", "Z", "SLOT"].map((r) => (
          <div key={r} className="role-box">
            <span className="kp-role">{r === "SLOT" ? "Slot" : r} receiver</span>
            {editing ? (
              <select
                aria-label={`${r} receiver`}
                value={draft[r]}
                onChange={(e) => setDraft((d) => ({ ...d, [r]: e.target.value }))}
              >
                <option value="">Automatic</option>
                {options.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.name}
                    {o.targets ? ` (${o.targets} tgt${o.adot != null ? `, aDOT ${o.adot}` : ""})` : ""}
                  </option>
                ))}
              </select>
            ) : (
              <strong>{info.starters[r]?.name || "–"}</strong>
            )}
            {!editing && info.starters[r]?.adot != null && (
              <span className="muted small">aDOT {info.starters[r].adot}</span>
            )}
          </div>
        ))}
      </div>
      <div className="role-actions">
        <span className="muted small">
          Set by: {info.method}
          {info.deep_threat ? ` · Deep threat: ${info.deep_threat.name}` : ""}
        </span>
        <div className="btns">
          {editing ? (
            <>
              <button className="btn" onClick={save}>Save roles</button>
              <button className="btn ghost" onClick={() => setEditing(false)}>Cancel</button>
            </>
          ) : (
            <>
              <button className="btn" onClick={start}>Edit roles</button>
              {info.method === "set by you" && (
                <button className="btn ghost" onClick={reset}>Use automatic</button>
              )}
            </>
          )}
        </div>
      </div>
      {status && <p className="muted small" role="status">{status}</p>}
    </Card>
  );
}
