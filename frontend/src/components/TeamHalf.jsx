import { Card, Chips, seasonHeading } from "./Common.jsx";
import StatTable from "./StatTable.jsx";
import RoleTable, { RbTable } from "./RoleTable.jsx";
import { CoverageBars, RunDirection, TdPodium } from "./Visuals.jsx";
import { KeyPlayers, LeaderTable } from "./Players.jsx";
import DepthChart from "./DepthChart.jsx";
import TeamLogo from "./TeamLogo.jsx";

const TABS = [
  ["offense", "Offense"],
  ["defense", "Defense"],
  ["depth", "Depth chart"],
];

export default function TeamHalf({ report, opponent, side, tab, onTab, seasons, notes, onRolesSaved }) {
  const t = report.team;
  const subtitle =
    tab === "offense"
      ? `What the ${opponent.team.name} defense has to stop`
      : tab === "defense"
      ? `What the ${opponent.team.name} offense will face`
      : "Latest ESPN depth chart";

  return (
    <article className="half" style={{ "--team": t.color, "--team2": t.color2 }} aria-label={`${t.full_name} ${tab}`}>
      <div className="half-top">
        <div className="half-title">
          <TeamLogo team={t} size={36} />
          <div>
            <h2>
              {t.name} {TABS.find(([k]) => k === tab)[1].toLowerCase()}
            </h2>
            <small>
              {side === "away" ? "Away" : "Home"} · {subtitle}
            </small>
          </div>
        </div>
        <div className="half-tabs" role="tablist">
          {TABS.map(([k, label]) => (
            <button key={k} role="tab" aria-selected={tab === k} onClick={() => onTab(k)}>
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="half-body">
        {seasons.length === 0 && <p className="muted">No seasons selected.</p>}
        {tab === "offense" && <Offense report={report} seasons={seasons} notes={notes} />}
        {tab === "defense" && <Defense report={report} seasons={seasons} notes={notes} />}
        {tab === "depth" && (
          <DepthChart report={report} seasons={seasons} notes={notes} onRolesSaved={onRolesSaved} />
        )}
      </div>
    </article>
  );
}

function Tendencies({ data, seasons, notes }) {
  return (
    <div className="tendencies">
      {seasons.map((s) => (
        <div key={s} className="tend-row">
          <span className="season-tag">{seasonHeading(s, seasons, notes)}</span>
          <Chips items={data?.[s]} />
        </div>
      ))}
    </div>
  );
}

function section(report, unit, id) {
  return report[unit].sections.find((s) => s.id === id);
}

function Offense({ report, seasons, notes }) {
  const o = report.offense;
  const S = (id) => section(report, "offense", id);
  return (
    <>
      <Card title="At a glance" desc="The offense's identity and what stands out.">
        <Tendencies data={o.tendencies} seasons={seasons} notes={notes} />
      </Card>

      <Card title="Key players" desc="Current starters from the depth chart, with each season's stats.">
        <KeyPlayers players={o.key_players} seasons={seasons} team={report.team.abbr} notes={notes} />
      </Card>

      <Card title="Who they target" desc="Target leaders and their receiver spot.">
        <LeaderTable leaders={o.leaders} kind="targets" seasons={seasons} limit={8} notes={notes} />
      </Card>

      <Card
        title="Production by receiver spot"
        desc="Which spot does the damage. Rank is yards per game among all 32 offenses."
      >
        <RoleTable roles={o.roles} seasons={seasons} side="off" notes={notes} />
      </Card>

      <Card
        title="Running backs: RB1, RB2, RB3, all"
        desc="Rushing plus receiving. Each game, the back with the most touches counts as RB1, the next as RB2. Names show who filled each spot most often."
      >
        <RbTable rows={o.rb_depth} seasons={seasons} side="off" notes={notes} />
      </Card>

      <Card title="Who scores the touchdowns" desc="Top 3 positions by touchdowns, then the players.">
        <TdPodium td={o.td} seasons={seasons} side="off" notes={notes} />
        <LeaderTable leaders={o.leaders} kind="td" seasons={seasons} limit={5} notes={notes} />
      </Card>

      <StatCard s={S("identity")} seasons={seasons} notes={notes} />
      <StatCard s={S("production")} seasons={seasons} notes={notes} />

      <StatCard s={S("rushing")} seasons={seasons} notes={notes}>
        <LeaderTable leaders={o.leaders} kind="rushers" seasons={seasons} limit={4} notes={notes} />
        <RunDirection data={o.run_dir} seasons={seasons} side="off" notes={notes} />
      </StatCard>

      <StatCard s={S("deep")} seasons={seasons} notes={notes}>
        <LeaderTable leaders={o.leaders} kind="deep" seasons={seasons} limit={4} notes={notes} />
      </StatCard>

      <StatCard s={S("redzone")} seasons={seasons} notes={notes}>
        <LeaderTable leaders={o.leaders} kind="rz" seasons={seasons} limit={5} notes={notes} />
      </StatCard>

      <StatCard s={S("protection")} seasons={seasons} notes={notes} />
    </>
  );
}

function Defense({ report, seasons, notes }) {
  const d = report.defense;
  const S = (id) => section(report, "defense", id);
  return (
    <>
      <Card title="At a glance" desc="How they like to play and where they bend.">
        <Tendencies data={d.tendencies} seasons={seasons} notes={notes} />
      </Card>

      <StatCard s={S("scheme")} seasons={seasons} notes={notes}>
        <CoverageBars shells={d.shells} seasons={seasons} notes={notes} />
      </StatCard>

      <Card
        title="Receiving yards allowed by receiver spot"
        desc="Passes caught only (RB rushing is in the running backs table below). Rank: 1 gives up the least, 32 the most."
      >
        <RoleTable roles={d.roles} seasons={seasons} side="def" notes={notes} />
      </Card>

      <Card
        title="Running backs allowed: RB1, RB2, RB3, all"
        desc="Rushing plus receiving by the opponent's lead back (RB1), backup (RB2) and anyone else. TDs include both. Rank: 32 gives up the most."
      >
        <RbTable rows={d.rb_depth} seasons={seasons} side="def" notes={notes} />
      </Card>

      <Card title="Touchdowns allowed" desc="The top 3 positions that score against them.">
        <TdPodium td={d.td} seasons={seasons} side="def" notes={notes} />
      </Card>

      <StatCard s={S("overall")} seasons={seasons} notes={notes} />

      <StatCard s={S("run")} seasons={seasons} notes={notes}>
        <RunDirection data={d.run_dir} seasons={seasons} side="def" notes={notes} />
      </StatCard>

      <StatCard s={S("deep")} seasons={seasons} notes={notes} />
      <StatCard s={S("redzone")} seasons={seasons} notes={notes} />
      <StatCard s={S("coverage")} seasons={seasons} notes={notes} />
    </>
  );
}

function StatCard({ s, seasons, notes, children }) {
  if (!s) return null;
  return (
    <Card title={s.title} desc={s.desc}>
      <StatTable rows={s.rows} seasons={seasons} notes={notes} />
      {children && <div className="card-extra">{children}</div>}
    </Card>
  );
}
