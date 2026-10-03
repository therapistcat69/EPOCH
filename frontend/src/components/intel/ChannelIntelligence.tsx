"use client";

import { useQuery } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import Link from "next/link";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card, ErrorBox, Loading, Stat, axisStyle } from "@/components/dashboard/ui";
import type { Range } from "@/lib/creator-api";
import { clock, compact, hours, pct } from "@/lib/format";
import { intel } from "@/lib/intel-api";
import { ContentPatternCard, ExperimentCard, GroqReportCard, List } from "./cards";

const num = (v: number | null | undefined, d = 1) => (v == null ? "Data unavailable" : v.toFixed(d));

export default function ChannelIntelligence({ range }: { range: Range }) {
  const q = useQuery({ queryKey: ["channel-report", range], queryFn: () => intel.channelReport(range) });
  const refresh = useQuery({ queryKey: ["channel-report-refresh", range], queryFn: () => intel.channelReport(range, true), enabled: false });
  const r = refresh.data ?? q.data;

  if (q.isLoading) return <Loading label="Building your channel report (this can take a few seconds)…" />;
  if (q.error) return <ErrorBox error={q.error} />;
  if (!r) return null;
  const o = r.overview;
  const cp = r.content_patterns;
  const ti = cp.transcript_insights;
  const retentionObs = r.performance_patterns.filter((p) => p.kind === "duration" || p.kind === "intro");

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs font-semibold tracking-[0.3em] text-red-500">CHANNEL INTELLIGENCE</p>
          <p className="text-sm text-neutral-500">{r.date_range.start} → {r.date_range.end} · {r.note}</p>
        </div>
        <button onClick={() => refresh.refetch()} disabled={refresh.isFetching} className="flex items-center gap-2 rounded-lg border border-neutral-400/40 px-3 py-2 text-sm">
          <RefreshCw className={`size-4 ${refresh.isFetching ? "animate-spin" : ""}`} /> Regenerate
        </button>
      </div>

      <h2 className="font-semibold">Channel health</h2>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-6">
        <Stat label="Videos analyzed" value={String(o.videos_analyzed)} sub={`of ${o.videos_in_library} in library`} />
        <Stat label="Average views" value={compact(o.average_views_per_video)} />
        <Stat label="Median views" value={compact(o.median_views_per_video)} />
        <Stat label="Avg view %" value={pct(o.average_view_percentage)} />
        <Stat label="Avg duration" value={clock(o.average_video_length_seconds)} />
        <Stat label="Uploads / month" value={o.uploads_per_month == null ? "—" : String(o.uploads_per_month)} />
      </div>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Total views" value={compact(o.total_views)} />
        <Stat label="Watch time" value={hours(o.total_watch_time_minutes)} />
        <Stat label="Net subscribers" value={o.net_subscribers == null ? "—" : String(o.net_subscribers)} />
        <Stat label="Avg view duration" value={clock(o.average_view_duration_seconds)} />
      </div>

      <h2 className="font-semibold">Content patterns</h2>
      <div className="grid gap-4 md:grid-cols-3">
        <ContentPatternCard title="Formats">
          <ul className="space-y-1 text-sm">{cp.formats.map((f) => <li key={f.format} className="flex justify-between"><span>{f.format}</span><span className="text-neutral-500">{f.count} · {(f.share * 100).toFixed(0)}%</span></li>)}</ul>
        </ContentPatternCard>
        <ContentPatternCard title="Title patterns (derived from your titles)">
          {cp.title_patterns.length ? <ul className="space-y-1 text-sm">{cp.title_patterns.map((p) => <li key={p.pattern} className="flex justify-between"><span>{p.pattern}</span><span className="text-neutral-500">{p.count}</span></li>)}</ul> : <p className="text-sm text-neutral-500">Not enough repeated patterns yet.</p>}
        </ContentPatternCard>
        <ContentPatternCard title="Recurring keywords"><p className="text-sm">{cp.keywords.join(" · ") || "Data unavailable"}</p></ContentPatternCard>
      </div>

      <Card title="Topics">
        {cp.topics.length === 0 ? <p className="text-sm text-neutral-500">Not enough videos to cluster topics.</p> : (
          <>
            <div className="h-56">
              <ResponsiveContainer>
                <BarChart data={cp.topics} layout="vertical" margin={{ left: 60 }}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                  <XAxis type="number" tick={axisStyle} />
                  <YAxis type="category" dataKey="topic" width={140} tick={axisStyle} />
                  <Tooltip />
                  <Bar dataKey="videos" name="Videos" fill="#ef4444" />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <table className="mt-2 w-full text-sm">
              <thead className="text-left text-xs uppercase text-neutral-500"><tr><th>Topic</th><th>Videos</th><th>Median views</th><th>Avg view %</th></tr></thead>
              <tbody>{cp.topics.map((t) => <tr key={t.topic} className="border-t border-neutral-400/20"><td className="py-1">{t.topic}</td><td>{t.videos}</td><td>{compact(t.median_views)}</td><td>{t.average_view_percentage == null ? "—" : pct(t.average_view_percentage)}</td></tr>)}</tbody>
            </table>
          </>
        )}
      </Card>

      <Card title="Performance patterns (observed associations)">
        {r.performance_patterns.length === 0 ? <p className="text-sm text-neutral-500">Not enough videos per group (minimum 3) to report patterns.</p> : <List items={r.performance_patterns.map((p) => p.statement)} />}
      </Card>

      <Card title="Retention patterns">
        {retentionObs.length === 0 ? <p className="text-sm text-neutral-500">Data unavailable — needs more videos with analytics (and transcripts for intro length).</p> : <List items={retentionObs.map((p) => p.statement)} />}
        <div className="mt-2 grid gap-2 text-sm md:grid-cols-3">
          {cp.common_video_lengths.map((g) => <div key={g.group} className="rounded border border-neutral-400/30 p-2"><b>{g.group}</b><br />{g.videos} videos · avg view % {g.average_view_percentage == null ? "—" : pct(g.average_view_percentage)}</div>)}
        </div>
      </Card>

      <Card title="Transcript insights">
        {ti.videos_with_transcripts === 0 ? <p className="text-sm text-neutral-500">No transcripts yet. Open a video and upload a transcript or audio to unlock these.</p> : (
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat label="Videos with transcript" value={String(ti.videos_with_transcripts)} />
            <Stat label="Avg intro (hook latency)" value={ti.average_intro_hook_seconds == null ? "—" : `${num(ti.average_intro_hook_seconds, 0)} s`} />
            <Stat label="Words per minute" value={num(ti.average_words_per_minute, 0)} />
            <Stat label="Common CTAs" value={ti.common_cta_types.join(", ") || "—"} />
          </div>
        )}
        {ti.recurring_themes.length > 0 && <p className="mt-2 text-sm text-neutral-500">Recurring themes: {ti.recurring_themes.join(" · ")}</p>}
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <Link href="/benchmark" className="rounded-xl border border-neutral-400/30 p-4 hover:bg-neutral-400/10"><b>Genre benchmarks →</b><p className="text-sm text-neutral-500">Compare this channel with a genre sample.</p></Link>
        <Link href="/trends" className="rounded-xl border border-neutral-400/30 p-4 hover:bg-neutral-400/10"><b>Trend opportunities →</b><p className="text-sm text-neutral-500">See what&apos;s visible in recent public content.</p></Link>
      </div>

      <GroqReportCard title="Groq channel report" state={r.groq}>
        {(g) => (
          <div className="space-y-3 text-sm">
            <p>{g.summary}</p>
            <div className="grid gap-3 md:grid-cols-2">
              <div><h4 className="font-semibold">Strengths</h4><List items={g.strengths} empty="None reported" /></div>
              <div><h4 className="font-semibold">Weaknesses</h4><List items={g.weaknesses} empty="None reported" /></div>
              <div><h4 className="font-semibold">Patterns</h4><List items={[...g.content_patterns, ...g.observed_performance_patterns]} empty="None reported" /></div>
              <div><h4 className="font-semibold">Experiments</h4><List items={g.experiments_to_try} empty="None reported" /></div>
            </div>
            <div className="space-y-2">{g.recommendations.map((x, i) => <ExperimentCard key={i} item={x} />)}</div>
          </div>
        )}
      </GroqReportCard>
    </div>
  );
}
