"use client";

import { useQuery } from "@tanstack/react-query";
import { CartesianGrid, Line, LineChart, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, type OwnedVideo, type Range, type RetentionPoint } from "@/lib/creator-api";
import { clock, pct } from "@/lib/format";
import { Card, Empty, ErrorBox, Loading, Stat, axisStyle } from "./ui";

export default function RetentionPanel({ video, range }: { video: OwnedVideo; range: Range }) {
  const ret = useQuery({ queryKey: ["retention", video.video_id], queryFn: () => api.retention(video.video_id) });
  const detail = useQuery({ queryKey: ["video", video.video_id, range], queryFn: () => api.videoDetail(video.video_id, range) });
  const duration = ret.data?.duration_seconds ?? video.duration_seconds ?? null;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Duration" value={clock(video.duration_seconds)} />
        <Stat label="Views (range)" value={detail.data?.metrics.views?.toLocaleString() ?? "—"} />
        <Stat label="Avg view %" value={pct(detail.data?.metrics.average_view_percentage)} />
        <Stat label="Avg view duration" value={clock(detail.data?.metrics.average_view_duration_seconds)} />
      </div>

      <Card title="Audience Retention Curve" right={<span className="text-xs text-neutral-500">Observed · YouTube Analytics</span>}>
        {ret.isLoading && <Loading label="Loading retention curve…" />}
        {ret.error && <ErrorBox error={ret.error} />}
        {ret.data && <Curve points={ret.data.points} duration={duration} drops={ret.data.observed_drop_offs} />}
      </Card>

      {ret.data && (
        <>
          <Card title="Relative Retention Performance">
            <p className="mb-2 text-sm text-neutral-500">
              How this video&apos;s audience retention compares with other videos of similar length. 1.0× means typical.
            </p>
            <div className="h-40">
              <ResponsiveContainer>
                <LineChart data={ret.data.points.map((p) => ({ t: p.time_ratio, v: p.relative_retention_performance }))}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                  <XAxis dataKey="t" type="number" domain={[0, 1]} tickFormatter={(v: number) => (duration ? clock(v * duration) : `${Math.round(v * 100)}%`)} tick={axisStyle} />
                  <YAxis tick={axisStyle} domain={[0, "auto"]} />
                  <Tooltip formatter={(v) => [`${Number(v).toFixed(2)}×`, "Relative performance"]} labelFormatter={(t) => (duration ? clock(Number(t) * duration) : `${(Number(t) * 100).toFixed(0)}%`)} />
                  <Line dataKey="v" stroke="#8b5cf6" dot={false} isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </Card>

          <Card title="Observed Drop-Offs">
            <p className="mb-2 text-sm text-neutral-500">Largest declines in actual audience watching. These are observations from YouTube, not predictions.</p>
            {ret.data.observed_drop_offs.length === 0 ? (
              <Empty>No declines observed.</Empty>
            ) : (
              <ol className="space-y-1 text-sm">
                {ret.data.observed_drop_offs.map((d, i) => (
                  <li key={i}>
                    {i + 1}. {duration ? `${clock(d.from_seconds)} → ${clock(d.to_seconds)}` : `${(d.from_ratio * 100).toFixed(0)}% → ${(d.to_ratio * 100).toFixed(0)}%`}:{" "}
                    <b>−{(d.drop * 100).toFixed(1)} pts</b> of the audience
                  </li>
                ))}
              </ol>
            )}
          </Card>
        </>
      )}

      <section className="rounded-xl border border-dashed border-neutral-400/50 p-5">
        <p className="text-xs font-semibold tracking-widest text-neutral-500">RETENTION PREDICTOR</p>
        <p className="mt-1 font-medium">Predicted by RetainAI — your ML model will appear here.</p>
        <p className="mt-1 text-sm text-neutral-500">
          Once connected, RetainAI will compare Actual YouTube Retention vs Predicted Retention. No predicted values are shown until then.
        </p>
      </section>
    </div>
  );
}

function Curve({ points, duration, drops }: { points: RetentionPoint[]; duration: number | null; drops: { from_ratio: number; to_ratio: number }[] }) {
  const label = (t: number) => (duration ? clock(t * duration) : `${(t * 100).toFixed(0)}%`);
  if (points.length === 0) return <Empty>No retention data.</Empty>;
  return (
    <div className="h-72">
      <ResponsiveContainer>
        <LineChart data={points}>
          <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
          <XAxis dataKey="time_ratio" type="number" domain={[0, 1]} tickFormatter={label} tick={axisStyle} />
          <YAxis domain={[0, "auto"]} tickFormatter={(v: number) => `${Math.round(v * 100)}%`} tick={axisStyle} />
          {drops.map((d, i) => (
            <ReferenceArea key={i} x1={d.from_ratio} x2={d.to_ratio} fill="#ef4444" fillOpacity={0.15} />
          ))}
          <Tooltip
            content={({ active, payload }) => {
              const p = payload?.[0]?.payload as RetentionPoint | undefined;
              if (!active || !p) return null;
              return (
                <div className="rounded-lg border border-neutral-400/40 bg-neutral-900 p-2 text-xs text-white">
                  <div className="font-semibold">{label(p.time_ratio)}</div>
                  <div>Audience watching: {p.audience_watch_ratio == null ? "—" : `${(p.audience_watch_ratio * 100).toFixed(1)}%`}</div>
                  <div>Relative performance: {p.relative_retention_performance == null ? "—" : `${p.relative_retention_performance.toFixed(2)}×`}</div>
                </div>
              );
            }}
          />
          <Line dataKey="audience_watch_ratio" stroke="#ef4444" strokeWidth={2} dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
      <p className="mt-1 text-xs text-neutral-500">Y axis: audience watching (audienceWatchRatio). Shaded areas: largest observed declines.</p>
    </div>
  );
}
