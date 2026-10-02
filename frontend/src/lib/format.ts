export const compact = (v: number | null | undefined) =>
  v == null ? "—" : new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 }).format(v);

export const num = (v: number | null | undefined) => (v == null ? "—" : new Intl.NumberFormat("en").format(v));

export const clock = (sec: number | null | undefined) => {
  if (sec == null) return "—";
  const s = Math.round(sec);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const r = s % 60;
  return h ? `${h}:${String(m).padStart(2, "0")}:${String(r).padStart(2, "0")}` : `${String(m).padStart(2, "0")}:${String(r).padStart(2, "0")}`;
};

// YouTube returns averageViewPercentage already as a percent (0-100)
export const pct = (v: number | null | undefined) => (v == null ? "—" : `${v.toFixed(1)}%`);

export const hours = (minutes: number | null | undefined) =>
  minutes == null ? "—" : `${new Intl.NumberFormat("en", { maximumFractionDigits: 1 }).format(minutes / 60)} h`;

export const iso = (d: Date) => {
  const z = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${z(d.getMonth() + 1)}-${z(d.getDate())}`;
};

export const rangeForDays = (days: number) => {
  const end = new Date();
  const start = new Date();
  start.setDate(end.getDate() - (days - 1));
  return { start: iso(start), end: iso(end) };
};

export const shortDate = (s: string | null) => (s ? s.slice(0, 10) : "—");
