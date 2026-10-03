"use client";

import { useQuery } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import { useState } from "react";
import { Card, ErrorBox, Loading } from "@/components/dashboard/ui";
import { compact } from "@/lib/format";
import { intel } from "@/lib/intel-api";
import { GroqReportCard, List } from "./cards";
import GenreControls, { DEFAULT_SELECTION, type Selection } from "./GenreControls";
import TrendCard from "./TrendCard";

export default function TrendRadar() {
  const [draft, setDraft] = useState<Selection>(DEFAULT_SELECTION);
  const [applied, setApplied] = useState<Selection | null>(null);
  const [ai, setAi] = useState(false);
  const [refreshNonce, setRefreshNonce] = useState(0);

  // Nothing is fetched until the user presses "Scan trends": search.list is quota-expensive.
  const q = useQuery({
    queryKey: ["trends", applied, ai, refreshNonce],
    queryFn: () => intel.trends({ ...applied!, subgenre: applied!.subgenre || undefined, include_ai: ai, refresh: refreshNonce > 0 }),
    enabled: !!applied,
    staleTime: 10 * 60 * 1000,
  });
  const d = q.data;

  return (
    <div className="space-y-4">
      <Card title="Trend Radar controls">
        <div className="flex flex-wrap items-end gap-3">
          <GenreControls value={draft} onChange={setDraft} />
          <label className="flex items-center gap-1 text-sm"><input type="checkbox" checked={ai} onChange={(e) => setAi(e.target.checked)} /> Add AI summary</label>
          <button onClick={() => setApplied(draft)} className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white">Scan trends</button>
          {applied && <button onClick={() => setRefreshNonce((n) => n + 1)} className="flex items-center gap-1 rounded-lg border border-neutral-400/40 px-3 py-2 text-sm" title="Bypass the cache (uses YouTube API quota)"><RefreshCw className="size-4" /> Refresh</button>}
        </div>
        <p className="mt-2 text-xs text-neutral-500">Results are cached (search is quota-expensive). The sample is recent public YouTube videos found through the official Data API.</p>
      </Card>

      {!applied && <p className="py-8 text-center text-sm text-neutral-500">Choose a genre and press “Scan trends”.</p>}
      {q.isLoading && <Loading label="Analyzing recent public videos…" />}
      {q.error && <ErrorBox error={q.error} />}

      {d && (
        <>
          <p className="text-sm text-neutral-500">
            {d.genre}{d.subgenre ? ` → ${d.subgenre}` : ""} · {d.sample_size} videos analyzed · median views {compact(d.genre_stats.median_views)} · {d.served_from_cache ? "served from cache" : `${d.search_calls_made} search call(s) made`}
          </p>
          <p className="text-xs text-neutral-500">{d.momentum_note}</p>

          <h2 className="text-lg font-semibold">Trending topics</h2>
          <div className="grid gap-4 lg:grid-cols-2">{d.topics.map((t) => <TrendCard key={t.topic} t={t} />)}</div>

          <Card title="Content opportunities">
            {d.opportunities.length === 0 ? <p className="text-sm text-neutral-500">No clear opportunities in this sample.</p> : (
              <div className="space-y-3">
                {d.opportunities.map((o) => (
                  <div key={o.title} className="rounded-lg border border-neutral-400/30 p-3 text-sm">
                    <p className="font-semibold">{o.title}</p>
                    <p>{o.statement}</p>
                    <List items={o.evidence} />
                  </div>
                ))}
              </div>
            )}
          </Card>

          {ai && (
            <GroqReportCard title="AI trend summary" state={d.ai_summary}>
              {(g) => (
                <div className="space-y-2 text-sm">
                  <p>{g.summary}</p>
                  {g.observed_opportunities.map((o, i) => <div key={i} className="rounded border border-neutral-400/30 p-2"><b>{o.title}</b><List items={o.evidence} /><p className="text-neutral-500">Experiment: {o.suggested_experiment}</p></div>)}
                  <List items={g.caveats} empty="" />
                </div>
              )}
            </GroqReportCard>
          )}
        </>
      )}
    </div>
  );
}
