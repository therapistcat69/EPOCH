"use client";

import { useQuery } from "@tanstack/react-query";
import { intel } from "@/lib/intel-api";

export type Selection = { genre: string; subgenre: string; language: string; region: string; time_window: string };
export const DEFAULT_SELECTION: Selection = { genre: "Technology", subgenre: "", language: "en", region: "IN", time_window: "30d" };

const sel = "rounded-lg border border-neutral-400/40 bg-transparent px-2 py-1.5 text-sm";

export default function GenreControls({ value, onChange }: { value: Selection; onChange: (s: Selection) => void }) {
  const cat = useQuery({ queryKey: ["genres"], queryFn: intel.genres, staleTime: Infinity });
  const subs = cat.data?.genres.find((g) => g.name === value.genre)?.subgenres ?? [];
  const set = (patch: Partial<Selection>) => onChange({ ...value, ...patch });
  const days: Record<string, string> = { "7d": "Last 7 days", "30d": "Last 30 days", "90d": "Last 90 days" };
  return (
    <div className="flex flex-wrap gap-2">
      <label className="text-xs text-neutral-500">Genre
        <select className={`${sel} block`} value={value.genre} onChange={(e) => set({ genre: e.target.value, subgenre: "" })}>
          {cat.data?.genres.map((g) => <option key={g.name} className="text-black">{g.name}</option>) ?? <option>{value.genre}</option>}
        </select>
      </label>
      <label className="text-xs text-neutral-500">Subgenre
        <select className={`${sel} block`} value={value.subgenre} onChange={(e) => set({ subgenre: e.target.value })}>
          <option value="" className="text-black">All</option>
          {subs.map((s) => <option key={s} className="text-black">{s}</option>)}
        </select>
      </label>
      <label className="text-xs text-neutral-500">Language
        <select className={`${sel} block`} value={value.language} onChange={(e) => set({ language: e.target.value })}>
          {cat.data?.languages.map((l) => <option key={l.code} value={l.code} className="text-black">{l.name}</option>)}
        </select>
      </label>
      <label className="text-xs text-neutral-500">Region
        <select className={`${sel} block`} value={value.region} onChange={(e) => set({ region: e.target.value })}>
          {cat.data?.regions.map((r) => <option key={r.code} value={r.code} className="text-black">{r.name}</option>)}
        </select>
      </label>
      <label className="text-xs text-neutral-500">Time range
        <select className={`${sel} block`} value={value.time_window} onChange={(e) => set({ time_window: e.target.value })}>
          {(cat.data?.time_windows ?? ["30d"]).map((w) => <option key={w} value={w} className="text-black">{days[w] ?? w}</option>)}
        </select>
      </label>
    </div>
  );
}
