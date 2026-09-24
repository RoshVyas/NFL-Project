import { formatGameTime } from "../format.js";
import TeamLogo from "./TeamLogo.jsx";

export default function MatchupHeader({ data }) {
  const { away, home, game } = data;
  const seasons = data.seasons.map(String);

  const record = (r) =>
    seasons
      .filter((s) => r.records[s])
      .map((s) => `${s}: ${r.records[s]}`)
      .join(" · ");

  let line = null;
  if (game?.spread_line != null) {
    const fav = game.spread_line > 0 ? home.team.abbr : away.team.abbr;
    line = `${fav} −${Math.abs(game.spread_line)}`;
  }

  return (
    <section className="matchup" aria-label="Matchup">
      <div className="team">
        <TeamLogo team={away.team} />
        <div>
          <h1>{away.team.name}</h1>
          <div className="rec">{record(away)}</div>
        </div>
      </div>
      <div className="vs">
        <b>@</b>
        {game ? (
          <>
            <small>
              Week {game.week} · {formatGameTime(game)}
            </small>
            {game.stadium && <small>{game.stadium}</small>}
            {(line || game.total_line) && (
              <small>
                {line}
                {line && game.total_line ? " · " : ""}
                {game.total_line ? `O/U ${game.total_line}` : ""}
              </small>
            )}
          </>
        ) : (
          <small>Custom matchup</small>
        )}
      </div>
      <div className="team right">
        <div>
          <h1>{home.team.name}</h1>
          <div className="rec">{record(home)}</div>
        </div>
        <TeamLogo team={home.team} />
      </div>
    </section>
  );
}
