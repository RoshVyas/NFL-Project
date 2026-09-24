import { useState } from "react";
import { fmt } from "../format.js";
import { RankPill, VerdictPill, seasonHeading } from "./Common.jsx";

export default function EdgeBoard({ data, seasons }) {
  const away = data.away.team;
  const home = data.home.team;
  return (
    <section className="edge-board" aria-label="Mismatches">
      <div className="section-head">
        <h2>Mismatches</h2>
        <p>
          Each offense's strengths against the other defense's weak spots. Ranks are 1–32 where 1 is best for that
          unit, so a low offense number next to a high defense number is an edge.
        </p>
      </div>
      <div className="edge-cols">
        <EdgeList edges={data.edges.away_offense} off={away} def={home} seasons={seasons} notes={data.season_notes} />
        <EdgeList edges={data.edges.home_offense} off={home} def={away} seasons={seasons} notes={data.season_notes} />
      </div>
    </section>
  );
}

function EdgeList({ edges, off, def, seasons, notes }) {
  const [all, setAll] = useState(false);
  // With one season shown, rank and label by that season alone; otherwise by the average of both.
  const single = seasons.length === 1 ? seasons[0] : null;
  const scoreOf = (e) => (single ? e.seasons[single]?.score ?? -1 : e.score);
  const verdictOf = (e) => (single ? e.seasons[single]?.verdict : e.verdict);
  const sorted = [...edges].sort((a, b) => scoreOf(b) - scoreOf(a));
  const shown = all ? sorted : sorted.slice(0, 6);
  return (
    <div className="edge-list" style={{ "--team": off.color, "--team2": off.color2 }}>
      <h3>
        <span className="swatch" /> {off.name} offense <span className="muted">vs</span> {def.name} defense
      </h3>
      <ul>
        {shown.map((e) => (
          <li key={e.key} className="edge-row">
            <div className="edge-main">
              <VerdictPill verdict={verdictOf(e)} />
              <div>
                <strong>{e.label}</strong>
                {e.player && <span className="edge-player">{e.player.name}</span>}
                <small className="muted">{e.metric_label}</small>
              </div>
            </div>
            <div className="edge-seasons">
              {seasons.map((s) => {
                const v = e.seasons[s];
                if (!v) return (
                  <div key={s} className="edge-season muted small">{s}: –</div>
                );
                return (
                  <div key={s} className="edge-season">
                    <span className="season-tag">{seasonHeading(s, seasons, notes)}</span>
                    <span title={`${off.name} offense: ${fmt(v.off_value, e.fmt)}`}>
                      {off.abbr} O <RankPill rank={v.off_rank} better="high" />
                    </span>
                    <span title={`${def.name} defense allows: ${fmt(v.def_value, e.fmt)}`}>
                      {def.abbr} D <RankPill rank={v.def_rank} better="high" />
                    </span>
                    <span className="edge-vals muted">
                      {fmt(v.off_value, e.fmt)} vs {fmt(v.def_value, e.fmt)} allowed
                    </span>
                  </div>
                );
              })}
            </div>
          </li>
        ))}
      </ul>
      {edges.length > 6 && (
        <button className="link" onClick={() => setAll((a) => !a)}>
          {all ? "Show fewer" : `Show all ${edges.length}`}
        </button>
      )}
    </div>
  );
}
