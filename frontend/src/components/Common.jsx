import { ordinal, tier, VERDICTS } from "../format.js";

export function RankPill({ rank, better, of = 32 }) {
  if (!rank) return null;
  const t = tier(rank, better);
  const title = better ? `${ordinal(rank)} of ${of} (1 = best)` : `${ordinal(rank)} highest of ${of}`;
  return (
    <span className={`pill ${t}`} title={title}>
      {rank}
    </span>
  );
}

export function Card({ title, desc, children, aside }) {
  return (
    <section className="card">
      {(title || aside) && (
        <div className="card-head">
          <div>
            {title && <h3>{title}</h3>}
            {desc && <p>{desc}</p>}
          </div>
          {aside}
        </div>
      )}
      {children}
    </section>
  );
}

export function Chips({ items }) {
  if (!items?.length) return null;
  return (
    <div className="chips">
      {items.map((c, i) => (
        <span key={i} className={`chip ${c.tone}`}>
          {c.text}
        </span>
      ))}
    </div>
  );
}

export function VerdictPill({ verdict }) {
  if (!verdict) return null;
  const v = VERDICTS[verdict];
  return <span className={`verdict ${v.tone}`}>{v.label}</span>;
}

export function seasonHeading(season, seasons, notes) {
  const last = seasons.length && season === String(Math.max(...seasons.map(Number)));
  const n = notes?.[season];
  if (last && n?.last_week && n.last_week < 18) return `${season} (wk 1–${n.last_week})`;
  return season;
}
