import { useState } from "react";

export default function TeamLogo({ team, size = 56 }) {
  const [failed, setFailed] = useState(false);
  const style = { width: size, height: size, "--team": team.color, "--team2": team.color2 };
  if (failed) {
    return (
      <div className="logo fallback" style={style} aria-label={team.full_name}>
        {team.abbr}
      </div>
    );
  }
  return <img className="logo" style={style} src={team.logo} alt={team.full_name} onError={() => setFailed(true)} />;
}
