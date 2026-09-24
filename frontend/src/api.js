async function request(path, options) {
  const res = await fetch(path, options);
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body.detail) detail = body.detail;
    } catch {
      /* not JSON */
    }
    throw new Error(detail);
  }
  return res.json();
}

export const api = {
  games: () => request("/api/games?days=7"),
  teams: () => request("/api/teams"),
  matchupByGame: (gameId) => request(`/api/matchup/${encodeURIComponent(gameId)}`),
  matchupByTeams: (away, home) =>
    request(`/api/matchup?away=${encodeURIComponent(away)}&home=${encodeURIComponent(home)}`),
  saveRoles: (team, season, roles) =>
    request(`/api/roles/${team}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ season, ...roles }),
    }),
  resetRoles: (team, season) => request(`/api/roles/${team}?season=${season}`, { method: "DELETE" }),
  refresh: () => request("/api/refresh", { method: "POST" }),
};
