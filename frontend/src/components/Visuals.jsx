import { seasonHeading } from "./Common.jsx";

const SHELL_COLORS = {
  COVER_0: "var(--c0)",
  COVER_1: "var(--c1)",
  "2_MAN": "var(--c2m)",
  COVER_2: "var(--c2)",
  COVER_3: "var(--c3)",
  COVER_4: "var(--c4)",
  COVER_6: "var(--c6)",
  OTHER: "var(--cx)",
};

export function CoverageBars({ shells, seasons, notes }) {
  const any = seasons.some((s) => shells?.[s]);
  const legend = seasons.map((s) => shells?.[s]).find(Boolean);
  return (
    <div className="cov">
      <h4>Coverage shells</h4>
      {seasons.map((s) => (
        <div className="cov-row" key={s}>
          <span className="lbl">{seasonHeading(s, seasons, notes)}</span>
          {shells?.[s] ? (
            <div className="bar" role="img" aria-label={shells[s].map((x) => `${x.label} ${x.pct}%`).join(", ")}>
              {shells[s].map((x) => (
                <span
                  key={x.key}
                  style={{ width: `${x.pct}%`, background: SHELL_COLORS[x.key] }}
                  title={`${x.label}: ${x.pct}%`}
                >
                  {x.pct >= 8 ? `${Math.round(x.pct)}%` : ""}
                </span>
              ))}
            </div>
          ) : (
            <span className="muted small">Published after the season</span>
          )}
        </div>
      ))}
      {any && legend && (
        <div className="legend">
          {legend.map((x) => (
            <span key={x.key}>
              <i style={{ background: SHELL_COLORS[x.key] }} />
              {x.label}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function ypcTone(ypc, carries, side) {
  if (ypc == null || carries < 5) return "none";
  const good = side === "off" ? ypc >= 5 : ypc <= 3.5;
  const bad = side === "off" ? ypc <= 3.5 : ypc >= 5;
  return good ? "good" : bad ? "bad" : "mid";
}

export function RunDirection({ data, seasons, side, notes }) {
  const first = seasons.map((s) => data?.[s]).find(Boolean);
  if (!first) return null;
  return (
    <div className="gaps">
      <h4>Yards per carry by run direction</h4>
      <div className="scroll">
        <div className="gap-grid" style={{ "--cols": first.length }}>
          <span />
          {first.map((b) => (
            <span key={b.key} className="h" title={b.label}>
              {b.key}
            </span>
          ))}
          {seasons.map((s) =>
            data?.[s] ? (
              <Row key={s} label={seasonHeading(s, seasons, notes)} buckets={data[s]} side={side} />
            ) : null
          )}
        </div>
      </div>
      <p className="muted small">
        LE/RE = outside the end, LT/RT = off tackle, LG/RG = guard, M = up the middle. Cells need 5+ carries to be
        colored. Hover a cell to see the number of carries.
      </p>
    </div>
  );
}

function Row({ label, buckets, side }) {
  return (
    <>
      <span className="lbl">{label}</span>
      {buckets.map((b) => (
        <span
          key={b.key}
          className={`cell pill ${ypcTone(b.ypc, b.carries, side)}`}
          title={`${b.label}: ${b.carries} carries`}
        >
          {b.ypc == null ? "–" : b.ypc.toFixed(1)}
        </span>
      ))}
    </>
  );
}

export function TdPodium({ td, seasons, notes, side }) {
  return (
    <div className={`season-cols n${seasons.length}`}>
      {seasons.map((s) => {
        const rows = td?.[s] || [];
        const total = rows.reduce((a, r) => a + r.td, 0);
        return (
          <div key={s} className="season-col">
            <div className="season-label">
              {seasonHeading(s, seasons, notes)} · {total} {side === "off" ? "TDs scored" : "TDs allowed"}
            </div>
            {rows.length === 0 && <p className="muted">No offensive TDs yet.</p>}
            <ol className="podium">
              {rows.slice(0, 3).map((r, i) => (
                <li key={r.key} className={`place p${i + 1}`}>
                  <span className="place-n">{i + 1}</span>
                  <span className="place-label">{r.label}</span>
                  <span className="place-val">
                    {r.td} <small>({Math.round(r.share)}%)</small>
                  </span>
                </li>
              ))}
            </ol>
            {rows.length > 3 && (
              <p className="muted small">
                Then: {rows.slice(3).map((r) => `${r.label} ${r.td}`).join(", ")}
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}
