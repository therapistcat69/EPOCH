"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Card, ErrorBox, Loading } from "@/components/dashboard/ui";
import { clock, rangeForDays } from "@/lib/format";
import { intel, type Benchmark } from "@/lib/intel-api";
import { ExperimentCard } from "./cards";
import GenreControls, { DEFAULT_SELECTION, type Selection } from "./GenreControls";

const show = (m: Benchmark["metrics"][number], v: number | null) => {
  if (v == null) return "Data unavailable";
  if (m.unit === "seconds") return clock(v);
  if (m.unit === "percent") return `${v.toFixed(1)}%`;
  return new Intl.NumberFormat("en", { maximumFractionDigits: 1 }).format(v);
};

export default function GenreBenchmark() {
  const [draft, setDraft] = useState<Selection>(DEFAULT_SELECTION);
  const [applied, setApplied] = useState<Selection | null>(null);
  const q = useQuery({
    queryKey: ["benchmark", applied],
    queryFn: () => intel.benchmark({ ...applied!, subgenre: applied!.subgenre || undefined }, rangeForDays(90)),
    enabled: !!applied,
    staleTime: 10 * 60 * 1000,
  });
  const b = q.data;

  return (
    <div className="space-y-4">
      <Card title="Compare my channel with a genre">
        <div className="flex flex-wrap items-end gap-3">
          <GenreControls value={draft} onChange={setDraft} />
          <button onClick={() => setApplied(draft)} className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white">Compare</button>
        </div>
      </Card>
      {!applied && <p className="py-8 text-center text-sm text-neutral-500">Pick a genre and press “Compare”.</p>}
      {q.isLoading && <Loading label="Comparing…" />}
      {q.error && <ErrorBox error={q.error} />}

      {b && (
        <>
          {b.message && <p className="rounded-lg border border-yellow-500/40 bg-yellow-500/10 p-3 text-sm">{b.message}</p>}
          <Card title="MY CHANNEL vs SELECTED GENRE">
            <table className="w-full text-sm">
              <thead className="text-left text-xs uppercase text-neutral-500"><tr><th>Metric</th><th>My channel</th><th>Genre sample</th><th>Difference</th></tr></thead>
              <tbody>
                {b.metrics.map((m) => (
                  <tr key={m.metric} className="border-t border-neutral-400/20 align-top">
                    <td className="py-2 pr-2">{m.metric}</td>
                    <td>{show(m, m.channel)}</td>
                    <td>{show(m, m.genre)}</td>
                    <td>{m.difference == null ? "—" : `${m.difference > 0 ? "+" : ""}${show(m, Math.abs(m.difference)).replace(/^/, m.difference < 0 ? "−" : "")}`}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="mt-3 space-y-2">
              {b.metrics.filter((m) => m.difference != null && m.statement).map((m) => (
                <ExperimentCard key={m.metric} item={{ observation: m.statement, interpretation: "", recommendation: m.suggested_experiment ?? "" }} />
              ))}
            </div>
            <p className="mt-3 text-xs text-neutral-500">{b.note}</p>
          </Card>
          <div className="grid gap-4 md:grid-cols-2">
            <Share title="Formats" rows={b.formats} />
            <Share title="Title patterns" rows={b.title_patterns} />
          </div>
        </>
      )}
    </div>
  );
}

function Share({ title, rows }: { title: string; rows: { name: string; channel_share: number; genre_share: number }[] }) {
  return (
    <Card title={title}>
      {rows.length === 0 ? <p className="text-sm text-neutral-500">Data unavailable</p> : (
        <table className="w-full text-sm">
          <thead className="text-left text-xs uppercase text-neutral-500"><tr><th></th><th>My channel</th><th>Genre</th></tr></thead>
          <tbody>{rows.map((r) => <tr key={r.name} className="border-t border-neutral-400/20"><td className="py-1">{r.name}</td><td>{(r.channel_share * 100).toFixed(0)}%</td><td>{(r.genre_share * 100).toFixed(0)}%</td></tr>)}</tbody>
        </table>
      )}
    </Card>
  );
}
