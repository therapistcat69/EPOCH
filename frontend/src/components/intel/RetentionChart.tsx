"use client";

import { CartesianGrid, Line, LineChart, ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { axisStyle } from "@/components/dashboard/ui";
import { clock } from "@/lib/format";
import type { DropOff, RetentionPt } from "@/lib/intel-api";

type Props = {
  points: RetentionPt[];
  duration: number | null;
  drops: DropOff[];
  currentTimestamp: number | null;
  onSelect: (seconds: number) => void;
};

/** Observed YouTube retention (raw points). Click a point -> shared currentTimestamp; the selected time is highlighted. */
export default function RetentionChart({ points, duration, drops, currentTimestamp, onSelect }: Props) {
  if (!points.length) return <p className="py-6 text-center text-sm text-neutral-500">Data unavailable</p>;
  const data = points.map((p) => ({
    t: duration ? p.time_ratio * duration : p.time_ratio,
    ratio: p.time_ratio,
    watch: p.audience_watch_ratio,
    rel: p.relative_retention_performance,
  }));
  const label = (t: number) => (duration ? clock(t) : `${(t * 100).toFixed(0)}%`);
  const max = duration ?? 1;
  return (
    <div className="h-72">
      <ResponsiveContainer>
        <LineChart
          data={data}
          onClick={(s: { activeIndex?: string | number | null }) => {
            const i = Number(s?.activeIndex);
            if (Number.isFinite(i) && data[i]) onSelect(data[i].t);
          }}
          style={{ cursor: "pointer" }}
        >
          <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
          <XAxis dataKey="t" type="number" domain={[0, max]} tickFormatter={label} tick={axisStyle} />
          <YAxis domain={[0, "auto"]} tickFormatter={(v: number) => `${Math.round(v * 100)}%`} tick={axisStyle} />
          {drops.map((d, i) => (
            <ReferenceArea key={i} x1={d.from_seconds ?? d.from_ratio * max} x2={d.to_seconds ?? d.to_ratio * max} fill="#ef4444" fillOpacity={0.15} />
          ))}
          {currentTimestamp != null && <ReferenceLine x={currentTimestamp} stroke="#8b5cf6" strokeWidth={2} label={{ value: label(currentTimestamp), fill: "#8b5cf6", fontSize: 11, position: "top" }} />}
          <Tooltip
            content={({ active, payload }) => {
              const p = payload?.[0]?.payload as (typeof data)[number] | undefined;
              if (!active || !p) return null;
              return (
                <div className="rounded-lg border border-neutral-400/40 bg-neutral-900 p-2 text-xs text-white">
                  <div className="font-semibold">{label(p.t)}</div>
                  <div>Audience watching: {p.watch == null ? "—" : `${(p.watch * 100).toFixed(1)}%`}</div>
                  <div>Relative performance: {p.rel == null ? "—" : `${p.rel.toFixed(2)}×`}</div>
                  <div className="text-neutral-400">Click to jump to this moment in the transcript</div>
                </div>
              );
            }}
          />
          <Line dataKey="watch" stroke="#ef4444" strokeWidth={2} dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
      <p className="mt-1 text-xs text-neutral-500">Observed audience watching (audienceWatchRatio). Shaded: largest observed declines. Purple line: selected moment.</p>
    </div>
  );
}
