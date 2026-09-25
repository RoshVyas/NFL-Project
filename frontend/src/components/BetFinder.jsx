import { useEffect, useMemo, useState } from "react";
import { api } from "../api.js";

// ---------- odds helpers ----------
export function parseOdds(text) {
  if (!text) return null;
  const t = String(text).trim();
  if (t.includes("/")) {
    const [a, b] = t.split("/").map(Number);
    return a > 0 && b > 0 ? 1 + a / b : null;
  }
  if (/^evens?$/i.test(t)) return 2;
  const d = Number(t);
  return d > 1 ? d : null;
}

// The fractional prices UK bookmakers actually use.
const LADDER = [
  "1/10", "1/8", "1/7", "1/6", "1/5", "2/9", "1/4", "2/7", "3/10", "1/3", "4/11", "2/5", "4/9", "1/2", "8/15",
  "4/7", "8/13", "4/6", "8/11", "4/5", "5/6", "10/11", "1/1", "11/10", "6/5", "5/4", "11/8", "6/4", "13/8",
  "7/4", "15/8", "2/1", "9/4", "5/2", "11/4", "3/1", "10/3", "7/2", "4/1", "9/2", "5/1", "11/2", "6/1", "13/2",
  "7/1", "15/2", "8/1", "17/2", "9/1", "10/1", "11/1", "12/1", "14/1", "16/1", "18/1", "20/1", "22/1", "25/1",
  "28/1", "33/1", "40/1", "50/1", "66/1", "80/1", "100/1", "150/1", "200/1",
].map((f) => {
  const [a, b] = f.split("/").map(Number);
  return { f, dec: 1 + a / b };
});

function toFraction(dec) {
  let best = LADDER[0];
  for (const r of LADDER) if (Math.abs(r.dec - dec) < Math.abs(best.dec - dec)) best = r;
  return best.f;
}

function fmtOdds(dec, mode) {
  if (!dec) return "–";
  if (mode === "frac") {
    const fr = toFraction(dec);
    return fr === "1/1" ? "Evens" : fr;
  }
  return dec.toFixed(2);
}
const pct = (p) => (p == null ? "–" : `${(p * 100).toFixed(0)}%`);
const evText = (ev) => (ev == null ? "–" : `${ev > 0 ? "+" : ""}${(ev * 100).toFixed(0)}%`);
const evTone = (ev) => (ev == null ? "" : ev > 0.02 ? "pos" : ev < -0.02 ? "neg" : "flat");

// bet365 prices typed in by the user, remembered per game in this browser
function useBet365(gameId) {
  const key = `b365:${gameId}`;
  const [vals, setVals] = useState({});
  useEffect(() => {
    try {
      setVals(JSON.parse(localStorage.getItem(key) || "{}"));
    } catch {
      setVals({});
    }
  }, [key]);
  const set = (id, v) =>
    setVals((cur) => {
      const next = { ...cur, [id]: v };
      try {
        localStorage.setItem(key, JSON.stringify(next));
      } catch {
        /* private mode */
      }
      return next;
    });
  return [vals, set];
}

export default function BetFinder({ gameId }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState(() => {
    try {
      return localStorage.getItem("odds-format") || "frac";
    } catch {
      return "frac";
    }
  });
  const [b365, setB365] = useBet365(gameId);

  const load = (refresh = false) => {
    if (!gameId) return;
    setLoading(true);
    setError(null);
    api
      .bets(gameId, refresh)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };
  useEffect(() => load(false), [gameId]); // eslint-disable-line react-hooks/exhaustive-deps

  const changeMode = (m) => {
    setMode(m);
    try {
      localStorage.setItem("odds-format", m);
    } catch {
      /* private mode */
    }
  };

  if (!gameId) {
    return (
      <div className="notice">
        The bet finder works on scheduled games. Pick a game from the Game list (not "Pick any two teams").
      </div>
    );
  }
  if (error) return <div className="notice error">Couldn't build picks: {error}</div>;
  if (!data) {
    return (
      <div className="loading-screen">
        <div className="spinner" aria-hidden="true" />
        <p>Running the numbers…</p>
      </div>
    );
  }

  const ctx = { mode, b365, setB365 };
  return (
    <section className={`bet-finder ${loading ? "is-loading" : ""}`} aria-label="Bet finder">
      <div className="section-head">
        <h2>Bet finder</h2>
        <p>
          Picks built from every stat in the dashboard. "Chance" is the model's probability, "Fair" is the price that
          probability is worth, and "Value" is how much the best price beats it. Type bet365's prices into the boxes to
          compare them with Paddy Power.
        </p>
      </div>

      <Header data={data} mode={mode} onMode={changeMode} onRefresh={() => load(true)} loading={loading} />

      <Card title="5 singles" desc="The strongest single bets, ranked by value × confidence.">
        <div className="pick-list">
          {data.singles.length === 0 && <p className="muted">No priced markets to choose from yet.</p>}
          {data.singles.map((s, i) => (
            <Pick key={s.id} n={i + 1} s={s} ctx={ctx} />
          ))}
        </div>
      </Card>

      <div className="bb-grid">
        <Builder title="Value bet builder" desc="High-probability legs that are each priced above fair." b={data.value_builder} id="value" ctx={ctx} />
        <Builder title="Longshot bet builder" desc="Bigger-price legs with value, aiming for 11/1 or more." b={data.longshot_builder} id="long" ctx={ctx} />
      </div>

      <div className="bb-grid">
        <TdList title="Top 3 anytime TD scorers" rows={data.td_top3} kind="any" ctx={ctx} />
        <TdList title="First TD scorer" rows={data.first_td} kind="first" ctx={ctx} />
      </div>

      <details className="card more">
        <summary>More picks ({data.all.length})</summary>
        <AllTable rows={data.all} ctx={ctx} />
      </details>

      <details className="card more">
        <summary>Player projections ({data.players.length})</summary>
        <Projections players={data.players} />
      </details>

      <Method data={data} />
    </section>
  );
}

function Card({ title, desc, children, aside }) {
  return (
    <section className="card">
      <div className="card-head">
        <div>
          <h3>{title}</h3>
          {desc && <p>{desc}</p>}
        </div>
        {aside}
      </div>
      <div className="card-body">{children}</div>
    </section>
  );
}

function Header({ data, mode, onMode, onRefresh, loading }) {
  const p = data.projection;
  const o = data.odds;
  const homeName = data.game.home_team.name;
  const awayName = data.game.away_team.name;
  const fav = p.margin >= 0 ? homeName : awayName;
  return (
    <div className="bf-head">
      <div className="card bf-proj">
        <div className="card-head">
          <div>
            <h3>Model projection</h3>
            <p>Expected score from both teams' scoring and points allowed, plus home field.</p>
          </div>
        </div>
        <div className="card-body proj-grid">
          <div>
            <span className="kp-role">{awayName}</span>
            <strong className="big">{p.away_pts}</strong>
          </div>
          <div>
            <span className="kp-role">{homeName}</span>
            <strong className="big">{p.home_pts}</strong>
          </div>
          <div>
            <span className="kp-role">Model line</span>
            <strong>
              {fav} by {Math.abs(p.margin).toFixed(1)}
            </strong>
            <small className="muted">
              Market: {p.market_spread_home == null ? "–" : `${homeName} ${p.market_spread_home > 0 ? "+" : ""}${p.market_spread_home}`}
            </small>
          </div>
          <div>
            <span className="kp-role">Total</span>
            <strong>{p.total}</strong>
            <small className="muted">Market: {p.market_total ?? "–"}</small>
          </div>
          <div>
            <span className="kp-role">{homeName} win</span>
            <strong>{pct(p.home_win)}</strong>
          </div>
        </div>
      </div>
      <div className="card bf-odds">
        <div className="card-head">
          <div>
            <h3>Odds</h3>
            <p>
              {o.source === "the-odds-api"
                ? `Live from The Odds API: ${o.books.join(", ")}.`
                : o.key_configured
                ? "No live odds for this game yet, so spread, total and money line use the US consensus."
                : "No Odds API key set, so only spread, total and money line are priced (US consensus). Add a key to get Paddy Power and player props."}
            </p>
          </div>
          <div className="seg small" role="group" aria-label="Odds format">
            <button aria-pressed={mode === "frac"} onClick={() => onMode("frac")}>5/6</button>
            <button aria-pressed={mode === "dec"} onClick={() => onMode("dec")}>1.83</button>
          </div>
        </div>
        <div className="card-body odds-meta">
          {o.error && <p className="notice error small">{o.error}</p>}
          <p className="muted small">
            {o.fetched_at ? `Fetched ${new Date(o.fetched_at).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}. ` : ""}
            {o.remaining != null ? `${o.remaining} Odds API credits left this month. ` : ""}
            {o.bet365_note}
          </p>
          {o.key_configured && (
            <button className="btn" onClick={onRefresh} disabled={loading}>
              {loading ? "Fetching…" : "Refresh odds"}
            </button>
          )}
          {data.unavailable.length > 0 && (
            <p className="small">
              <strong>Left out (injury):</strong>{" "}
              {data.unavailable.map((u) => `${u.name} (${u.team}, ${u.status})`).join(", ")}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function PriceCells({ s, ctx, id }) {
  const { mode, b365, setB365 } = ctx;
  const b = parseOdds(b365[id]);
  const pp = s.prices?.paddypower;
  const best = b && pp ? (b > pp ? "bet365" : b < pp ? "Paddy Power" : "Same") : b ? "bet365" : pp ? "Paddy Power" : null;
  const top = Math.max(b || 0, pp || 0) || s.price_used;
  const ev = top ? s.p * top - 1 : null;
  return (
    <>
      <div className="px">
        <span className="px-l">Chance</span>
        <strong>{pct(s.p)}</strong>
      </div>
      <div className="px">
        <span className="px-l">Fair</span>
        <strong>{fmtOdds(s.fair_odds, mode)}</strong>
      </div>
      <div className="px">
        <span className="px-l">Paddy Power</span>
        <strong>{fmtOdds(pp, mode)}</strong>
        {!pp && s.price_source && s.price_source !== "Paddy Power" && (
          <small className="muted" title="No Paddy Power price; this is the reference price used for value">
            {s.price_source === "estimated" ? `est. ${fmtOdds(s.price_used, mode)}` : `${s.price_source} ${fmtOdds(s.price_used, mode)}`}
          </small>
        )}
      </div>
      <label className="px">
        <span className="px-l">bet365</span>
        <input
          className="b365"
          inputMode="decimal"
          placeholder={mode === "frac" ? "e.g. 5/6" : "e.g. 1.83"}
          value={b365[id] || ""}
          onChange={(e) => setB365(id, e.target.value)}
          aria-label={`bet365 odds for ${s.label}`}
        />
      </label>
      <div className="px">
        <span className="px-l">Value</span>
        <strong className={`ev ${evTone(ev)}`}>{evText(ev)}</strong>
        {best && <small className="muted">Best: {best}</small>}
      </div>
    </>
  );
}

function Pick({ n, s, ctx }) {
  return (
    <article className="pick">
      <div className="pick-main">
        <span className="pick-n">{n}</span>
        <div>
          <div className="pick-label">{s.label}</div>
          <div className="pick-meta">
            {s.market_label}
            {s.est_line && (
              <span className="tag warn" title="No bookmaker line was available, so the line and price are estimated from the player's own average. Check bet365's line before betting.">
                Estimated line
              </span>
            )}
            {s.value_flag === "thin" && <span className="tag">Thin value</span>}
          </div>
          {s.reasons?.length > 0 && (
            <ul className="reasons">
              {s.reasons.map((r, i) => (
                <li key={i}>{r}</li>
              ))}
            </ul>
          )}
        </div>
      </div>
      <div className="pick-prices">
        <PriceCells s={s} ctx={ctx} id={s.id} />
      </div>
    </article>
  );
}

function Builder({ title, desc, b, id, ctx }) {
  const { mode, b365, setB365 } = ctx;
  if (!b) {
    return (
      <Card title={title} desc={desc}>
        <p className="muted">Not enough priced legs with value for this game yet.</p>
      </Card>
    );
  }
  const bid = `bb-${id}`;
  const b365price = parseOdds(b365[bid]);
  const ev = b365price ? b.p * b365price - 1 : b.ev;
  return (
    <Card title={title} desc={desc}>
      <ol className="legs">
        {b.legs.map((l) => (
          <li key={l.id}>
            <span>{l.label}</span>
            <span className="muted small">
              {pct(l.p)} · {fmtOdds(l.price_used, mode)}
              {l.est_line ? " (est. line)" : ""}
            </span>
          </li>
        ))}
      </ol>
      <div className="bb-sum">
        <div className="px">
          <span className="px-l">Chance</span>
          <strong>{pct(b.p)}</strong>
        </div>
        <div className="px">
          <span className="px-l">Fair</span>
          <strong>{fmtOdds(b.fair_odds, mode)}</strong>
        </div>
        <div className="px">
          <span className="px-l">Legs multiplied</span>
          <strong>{fmtOdds(b.price, mode)}</strong>
        </div>
        <label className="px">
          <span className="px-l">bet365 builder</span>
          <input
            className="b365"
            inputMode="decimal"
            placeholder={mode === "frac" ? "e.g. 9/2" : "e.g. 5.5"}
            value={b365[bid] || ""}
            onChange={(e) => setB365(bid, e.target.value)}
            aria-label={`bet365 price for ${title}`}
          />
        </label>
        <div className="px">
          <span className="px-l">Value</span>
          <strong className={`ev ${evTone(ev)}`}>{evText(ev)}</strong>
        </div>
      </div>
      <p className="muted small">{b.note}</p>
    </Card>
  );
}

function TdList({ title, rows, kind, ctx }) {
  const { mode, b365, setB365 } = ctx;
  return (
    <Card title={title} desc={kind === "any" ? "Most likely to score at any point." : "Most likely to score the game's first touchdown."}>
      <ol className="td-list">
        {rows.map((r, i) => {
          const id = `${kind}-${r.player_id}`;
          const p = kind === "any" ? r.p_any : r.p_first;
          const f = kind === "any" ? r.fair_any : r.fair_first;
          const pp = (kind === "any" ? r.prices_any : r.prices_first)?.paddypower;
          const b = parseOdds(b365[id]);
          const top = Math.max(b || 0, pp || 0);
          const ev = top ? p * top - 1 : null;
          return (
            <li key={id} className="td-row">
              <span className="pick-n">{i + 1}</span>
              <div className="td-name">
                <strong>{r.player}</strong>
                <small className="muted">
                  {r.team} · {r.role}
                  {r.injury ? ` · ${r.injury.status}` : ""}
                </small>
              </div>
              <div className="px">
                <span className="px-l">Chance</span>
                <strong>{pct(p)}</strong>
              </div>
              <div className="px">
                <span className="px-l">Fair</span>
                <strong>{fmtOdds(f, mode)}</strong>
              </div>
              <div className="px">
                <span className="px-l">Paddy Power</span>
                <strong>{fmtOdds(pp, mode)}</strong>
              </div>
              <label className="px">
                <span className="px-l">bet365</span>
                <input
                  className="b365"
                  inputMode="decimal"
                  placeholder={mode === "frac" ? "e.g. 6/4" : "e.g. 2.5"}
                  value={b365[id] || ""}
                  onChange={(e) => setB365(id, e.target.value)}
                  aria-label={`bet365 odds for ${r.player}`}
                />
              </label>
              <div className="px">
                <span className="px-l">Value</span>
                <strong className={`ev ${evTone(ev)}`}>{evText(ev)}</strong>
              </div>
            </li>
          );
        })}
      </ol>
    </Card>
  );
}

function AllTable({ rows, ctx }) {
  const { mode } = ctx;
  return (
    <div className="scroll">
      <table className="stat-table">
        <thead>
          <tr>
            <th>Bet</th>
            <th>Market</th>
            <th className="num">Chance</th>
            <th className="num">Fair</th>
            <th className="num">Price used</th>
            <th className="num">Value</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((s) => (
            <tr key={s.id}>
              <td className="label">
                {s.label}
                {s.est_line && <small>Estimated line</small>}
              </td>
              <td>{s.market_label}</td>
              <td className="num">{pct(s.p)}</td>
              <td className="num">{fmtOdds(s.fair_odds, mode)}</td>
              <td className="num">
                {fmtOdds(s.price_used, mode)} <small className="muted">{s.price_source}</small>
              </td>
              <td className={`num ev ${evTone(s.ev)}`}>{evText(s.ev)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Projections({ players }) {
  const sorted = useMemo(() => [...players].sort((a, b) => a.team.localeCompare(b.team) || b.p_any - a.p_any), [players]);
  return (
    <div className="scroll">
      <table className="stat-table">
        <thead>
          <tr>
            <th>Player</th>
            <th className="num">Pass yds</th>
            <th className="num">Pass TD</th>
            <th className="num">Rush yds</th>
            <th className="num">Rec</th>
            <th className="num">Rec yds</th>
            <th className="num">Anytime TD</th>
            <th className="num">First TD</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((p) => (
            <tr key={p.id}>
              <td className="label">
                {p.name} <span className="tag">{p.role === "SLOT" ? "Slot" : p.role}</span>
                <small>
                  {p.team}
                  {p.injury ? ` · ${p.injury}` : ""}
                </small>
              </td>
              <td className="num">{p.pos === "QB" ? p.pass_yds.toFixed(0) : "–"}</td>
              <td className="num">{p.pos === "QB" ? p.pass_td.toFixed(1) : "–"}</td>
              <td className="num">{p.rush_yds.toFixed(0)}</td>
              <td className="num">{p.pos === "QB" ? "–" : p.rec.toFixed(1)}</td>
              <td className="num">{p.pos === "QB" ? "–" : p.rec_yds.toFixed(0)}</td>
              <td className="num">{pct(p.p_any)}</td>
              <td className="num">{pct(p.p_first)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Method({ data }) {
  const w = data.weights;
  return (
    <details className="card more">
      <summary>How the picks are worked out</summary>
      <div className="card-body method">
        <ol>
          <li>
            <strong>Score projection.</strong> Each team's expected points = its scoring rate × what the opponent allows,
            relative to the league average, plus home field. This season counts for{" "}
            {Object.entries(w.current_season_weight)
              .map(([t, v]) => `${Math.round(v * 100)}% (${t})`)
              .join(" and ")}{" "}
            against last season, rising as more games are played.
          </li>
          <li>
            <strong>Player projections.</strong> Yards, catches and TDs from each player's own averages, adjusted by what
            this opponent allows to his spot (X, Z, slot, TE, RB, QB). TD chances come from his share of team TDs and
            red-zone chances. Players listed Out or Doubtful are removed; Questionable players count for less.
          </li>
          <li>
            <strong>Probabilities.</strong> Yards use a bell curve and counts use a Poisson distribution. Where
            bookmakers have a line, the model is blended with their no-vig probability (model weight{" "}
            {Math.round(w.model_weight_main * 100)}% for spread, total and money line; more for props and TDs) so one noisy
            stat can't invent value.
          </li>
          <li>
            <strong>Ranking.</strong> Value = chance × odds − 1. Picks are ranked by value × confidence. Confidence rises
            with sample size and when the matchup stats agree (the Mismatches board), and drops for estimated lines and
            reference prices.
          </li>
          <li>
            <strong>Bet builders</strong> multiply leg prices as if the legs were independent. bet365 prices builders with
            its own adjustments, so enter its builder price to see the true value.
          </li>
        </ol>
        <p className="muted small">
          This is a statistical model, not a guarantee. Bet only what you can afford to lose. Help is at{" "}
          <a href="https://www.begambleaware.org" target="_blank" rel="noreferrer">
            BeGambleAware.org
          </a>
          .
        </p>
      </div>
    </details>
  );
}
