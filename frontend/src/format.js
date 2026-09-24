export function fmt(v, kind) {
  if (v === null || v === undefined || Number.isNaN(v)) return "–";
  switch (kind) {
    case "pct":
      return `${v.toFixed(1)}%`;
    case "epa":
      return `${v > 0 ? "+" : ""}${v.toFixed(2)}`;
    case "n0":
      return `${Math.round(v)}`;
    default:
      return v.toFixed(1);
  }
}

// Rank 1 is always best for the unit being shown (or highest for neutral stats).
export function tier(rank, better) {
  if (!rank) return "none";
  if (!better) return "neutral";
  if (rank <= 8) return "good";
  if (rank >= 25) return "bad";
  return "mid";
}

export function ordinal(n) {
  const s = ["th", "st", "nd", "rd"];
  const v = n % 100;
  return n + (s[(v - 20) % 10] || s[v] || s[0]);
}

export const VERDICTS = {
  big_edge: { label: "Big edge", tone: "good-strong" },
  edge: { label: "Edge", tone: "good" },
  even: { label: "Even", tone: "neutral" },
  tough: { label: "Tough", tone: "bad" },
};

export const ROLE_SHORT = { X: "X", Z: "Z", SLOT: "Slot", WR: "WR", TE: "TE", RB: "RB" };

export function formatGameTime(game) {
  if (!game) return "";
  const d = new Date(`${game.gameday}T12:00:00`);
  const day = d.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
  if (!game.gametime) return day;
  const [h, m] = game.gametime.split(":").map(Number);
  const hr = ((h + 11) % 12) + 1;
  return `${day} · ${hr}:${String(m).padStart(2, "0")} ${h >= 12 ? "PM" : "AM"} ET`;
}
