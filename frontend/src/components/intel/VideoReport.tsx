"use client";

import { useQuery } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import { useState } from "react";
import { Card, ErrorBox, Loading, Stat } from "@/components/dashboard/ui";
import { clock, compact, pct } from "@/lib/format";
import { intel } from "@/lib/intel-api";
import PredictedRetention, { useVideoPrediction } from "@/components/ml/PredictedRetention";
import { ExperimentCard, GroqReportCard, List } from "./cards";
import ObservedDropoffCard from "./ObservedDropoffCard";
import RetentionChart from "./RetentionChart";
import TranscriptViewer from "./TranscriptViewer";

const sec = (v: number | null | undefined) => (v == null ? "Data unavailable" : `${v.toFixed(0)} s`);

export default function VideoReport({ videoId }: { videoId: string }) {
  const [currentTimestamp, setCurrentTimestamp] = useState<number | null>(null); // shared UI state: transcript <-> retention
  const q = useQuery({ queryKey: ["video-report", videoId], queryFn: () => intel.videoReport(videoId) });
  const refresh = useQuery({ queryKey: ["video-report-refresh", videoId], queryFn: () => intel.videoReport(videoId, true), enabled: false });
  const r = refresh.data ?? q.data;
  const pred = useVideoPrediction(videoId, false); // shared with the Predicted retention panel (same query key)

  if (q.isLoading) return <Loading label="Building your video report (this can take a few seconds)…" />;
  if (q.error) return <ErrorBox error={q.error} />;
  if (!r) return null;
  const v = r.video;
  const segs = r.features?.segments ?? [];
  const transcriptSegs = segs.map((s) => ({ segment_index: s.segment_id, start_seconds: s.start, end_seconds: s.end, text: s.text }));
  const drops = r.retention.observed_drop_offs;
  const predicted = pred.data && pred.data.available ? pred.data.prediction.risk_segments : [];

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap gap-4">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        {v.thumbnail_url && <img src={v.thumbnail_url} alt="" className="h-28 rounded-lg" />}
        <div className="min-w-0 flex-1">
          <p className="text-xs font-semibold tracking-[0.3em] text-red-500">VIDEO INTELLIGENCE</p>
          <h1 className="text-2xl font-bold">{v.title}</h1>
          <p className="text-sm text-neutral-500">{v.channel} · {clock(v.duration_seconds)}</p>
        </div>
        <button onClick={() => refresh.refetch()} disabled={refresh.isFetching} className="flex h-9 items-center gap-2 self-start rounded-lg border border-neutral-400/40 px-3 text-sm">
          <RefreshCw className={`size-4 ${refresh.isFetching ? "animate-spin" : ""}`} /> Regenerate
        </button>
      </header>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Views" value={compact(v.views)} />
        <Stat label="Avg view %" value={pct(r.analytics.metrics.average_view_percentage)} />
        <Stat label="Avg view duration" value={clock(r.analytics.metrics.average_view_duration_seconds)} />
        <Stat label="Likes / comments" value={`${compact(v.likes)} / ${compact(v.comments)}`} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Observed audience retention" right={<span className="text-xs text-neutral-500">YouTube Analytics</span>}>
          {r.retention.available ? (
            <RetentionChart points={r.retention.points} duration={v.duration_seconds} drops={drops} currentTimestamp={currentTimestamp} onSelect={setCurrentTimestamp} />
          ) : (
            <p className="py-6 text-center text-sm text-neutral-500">Data unavailable{r.retention.message ? ` — ${r.retention.message}` : ""}</p>
          )}
        </Card>
        <Card title="Transcript" right={r.transcript.provider ? <span className="text-xs text-neutral-500">{r.transcript.provider}{r.transcript.language ? ` · ${r.transcript.language}` : ""}</span> : undefined}>
          <TranscriptViewer
            videoId={videoId} available={r.transcript.available} segments={transcriptSegs} features={segs} drops={drops}
            currentTimestamp={currentTimestamp} onSelect={setCurrentTimestamp} riskRegions={predicted} estimated={r.transcript.timestamps_estimated}
            message={r.transcript.message} onChanged={() => { q.refetch(); }}
          />
        </Card>
      </div>

      <Card title="Observed audience changes">
        <ObservedDropoffCard drops={drops} onSelect={setCurrentTimestamp} />
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <Card title="Hook analysis">
          {r.hook ? (
            <dl className="space-y-1 text-sm">
              <Row k="Hook latency" v={sec(r.hook.hook_latency_seconds)} />
              <Row k="First concrete payoff" v={sec(r.hook.first_payoff_seconds)} />
              <Row k="First topic reveal" v={sec(r.hook.first_topic_reveal_seconds)} />
            </dl>
          ) : <p className="text-sm text-neutral-500">Needs a transcript.</p>}
        </Card>
        <Card title="Promise gap">
          {r.promise_gap ? (
            <>
              <p className="text-2xl font-semibold">{sec(r.promise_gap.promise_gap_seconds)}</p>
              <p className="mt-1 text-xs text-neutral-500">Time until the title&apos;s promise starts to be addressed. {r.promise_gap.note}</p>
            </>
          ) : <p className="text-sm text-neutral-500">Needs a transcript.</p>}
        </Card>
        <Card title="Pacing">
          {r.pacing ? (
            <dl className="space-y-1 text-sm">
              <Row k="Words per minute" v={r.pacing.average_words_per_minute?.toFixed(0) ?? "Data unavailable"} />
              <Row k="Sentences per minute" v={r.pacing.sentences_per_minute?.toFixed(1) ?? "Data unavailable"} />
              <Row k="Average segment" v={sec(r.pacing.mean_segment_seconds)} />
              <Row k="Topic transitions" v={String(r.pacing.topic_transitions)} />
              <Row k="Silence" v="Data unavailable (needs audio)" />
            </dl>
          ) : <p className="text-sm text-neutral-500">Needs a transcript.</p>}
        </Card>
        <Card title="Repetition">
          {r.repetition ? (
            r.repetition.repeated_ideas.length ? (
              <ul className="space-y-1 text-sm">
                {r.repetition.repeated_ideas.map((x, i) => (
                  <li key={i}><button className="underline" onClick={() => setCurrentTimestamp(x.start)}>{clock(x.start)}–{clock(x.end)}</button> repeats earlier wording (similarity {x.similarity})</li>
                ))}
              </ul>
            ) : <p className="text-sm text-neutral-500">No closely repeated segments found.</p>
          ) : <p className="text-sm text-neutral-500">Needs a transcript.</p>}
        </Card>
        <Card title="CTA analysis">
          {r.cta ? (
            r.cta.ctas.length ? (
              <ul className="space-y-1 text-sm">
                {r.cta.ctas.map((c, i) => <li key={i}><button className="underline" onClick={() => setCurrentTimestamp(c.start)}>{clock(c.start)}</button> · {c.type}</li>)}
              </ul>
            ) : <p className="text-sm text-neutral-500">No calls to action detected.</p>
          ) : <p className="text-sm text-neutral-500">Needs a transcript.</p>}
        </Card>
      </div>

      <GroqReportCard title="Groq review" state={r.groq}>
        {(g) => (
          <div className="space-y-3 text-sm">
            <p>{g.summary}</p>
            <div className="grid gap-3 md:grid-cols-2">
              <div><h4 className="font-semibold">Strengths</h4><List items={g.strengths} empty="None reported" /></div>
              <div><h4 className="font-semibold">Weaknesses</h4><List items={g.weaknesses} empty="None reported" /></div>
            </div>
            {g.recommendations.map((x, i) => (
              <div key={i} className="rounded-lg border border-neutral-400/30 p-3">
                <b className="uppercase">{x.type}</b>
                {x.start != null && <button className="ml-2 underline" onClick={() => setCurrentTimestamp(x.start!)}>{clock(x.start)}{x.end != null ? `–${clock(x.end)}` : ""}</button>}
                <p>{x.reason}</p>
                <p className="text-neutral-500">Evidence: {x.evidence}</p>
                {x.confidence != null && <p className="text-xs text-neutral-500">Model confidence (self-reported, not a statistic): {x.confidence}</p>}
              </div>
            ))}
          </div>
        )}
      </GroqReportCard>

      <Card title="Recommended experiments">
        {r.experiments.length ? <div className="space-y-2">{r.experiments.map((e, i) => <ExperimentCard key={i} item={e} />)}</div> : <p className="text-sm text-neutral-500">No experiments suggested by the data (needs a transcript for most checks).</p>}
      </Card>

      <PredictedRetention videoId={videoId} currentTimestamp={currentTimestamp} onSelect={setCurrentTimestamp} />
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return <div className="flex justify-between border-b border-neutral-400/20 py-1"><dt className="text-neutral-500">{k}</dt><dd className="font-medium">{v}</dd></div>;
}
