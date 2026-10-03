"use client";

import { Area, CartesianGrid, ComposedChart, Line, ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { axisStyle } from "@/components/dashboard/ui";
import { clock } from "@/lib/format";
import type { Prediction } from "@/lib/ml-api";

type Props = {
  prediction: Prediction;
  /** Observed (or synthetic) reference curve on normalized time ratios, in percent. */
  reference?: { time_ratio: number; value: number }[];
  referenceLabel: string; // "Actual YouTube retention" | "Synthetic target"
  currentTimestamp: number | null;
  onSelect: (seconds: number) => void;
};

/** Predicted (violet) vs observed/synthetic reference (red). Risk regions are violet bands; observed and predicted stay visually separate. */
export default function PredictionChart({ prediction, reference, referenceLabel, currentTimestamp, onSelect }: Props) {
  const dur = prediction.duration_seconds;
  const interp = (curve: { time_ratio: number; value: number }[] | undefined, r: number) => {
    if (!curve || curve.length === 0) return null;
    if (r <= curve[0].time_ratio) return curve[0].value;
    for (let i = 1; i < curve.length; i++) {
      if (r <= curve[i].time_ratio) {
        const a = curve[i - 1], b = curve[i];
        return a.value + ((b.value - a.value) * (r - a.time_ratio)) / Math.max(b.time_ratio - a.time_ratio, 1e-9);
      }
    }
    return curve[curve.length - 1].value;
  };
  const unc = prediction.uncertainty;
  const pts = prediction.points;
  const bandAt = (arr: number[], r: number) => {
    if (!unc.available || arr.length !== pts.length) return null;
    const x = r * dur;
    let k = 0;
    while (k < pts.length - 1 && pts[k + 1].start_seconds <= x) k++;
    return arr[k];
  };
  const data = prediction.normalized_curve.map((p) => {
    const lo = bandAt(unc.lower, p.time_ratio), hi = bandAt(unc.upper, p.time_ratio);
    return {
      t: p.time_ratio * dur,
      predicted: p.predicted_retention,
      reference: interp(reference, p.time_ratio),
      band: lo != null && hi != null ? [lo, hi] : undefined,
    };
  });

  return (
    <div className="h-80">
      <ResponsiveContainer>
        <ComposedChart
          data={data}
          onClick={(s: { activeIndex?: string | number | null }) => {
            const i = Number(s?.activeIndex);
            if (Number.isFinite(i) && data[i]) onSelect(data[i].t);
          }}
          style={{ cursor: "pointer" }}
        >
          <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
          <XAxis dataKey="t" type="number" domain={[0, dur]} tickFormatter={(v: number) => clock(v)} tick={axisStyle} />
          <YAxis domain={[0, 100]} tickFormatter={(v: number) => `${v}%`} tick={axisStyle} />
          {prediction.risk_segments.map((r, i) => (
            <ReferenceArea key={i} x1={r.start_seconds} x2={r.end_seconds} fill="#8b5cf6" fillOpacity={0.18} stroke="#8b5cf6" strokeOpacity={0.5} />
          ))}
          {currentTimestamp != null && <ReferenceLine x={currentTimestamp} stroke="#f59e0b" strokeWidth={2} />}
          {unc.available && <Area dataKey="band" stroke="none" fill="#8b5cf6" fillOpacity={0.12} isAnimationActive={false} />}
          {reference && <Line dataKey="reference" name={referenceLabel} stroke="#ef4444" strokeWidth={2} dot={false} isAnimationActive={false} />}
          <Line dataKey="predicted" name="Model prediction" stroke="#8b5cf6" strokeWidth={2.5} strokeDasharray="6 3" dot={false} isAnimationActive={false} />
          <Tooltip
            content={({ active, payload }) => {
              const p = payload?.[0]?.payload as (typeof data)[number] | undefined;
              if (!active || !p) return null;
              return (
                <div className="rounded-lg border border-neutral-400/40 bg-neutral-900 p-2 text-xs text-white">
                  <div className="font-semibold">{clock(p.t)}</div>
                  <div className="text-violet-300">Predicted: {p.predicted.toFixed(1)}%</div>
                  {p.reference != null && <div className="text-red-300">{referenceLabel}: {p.reference.toFixed(1)}%</div>}
                  <div className="text-neutral-400">Click to jump in the transcript</div>
                </div>
              );
            }}
          />
        </ComposedChart>
      </ResponsiveContainer>
      <div className="mt-1 flex flex-wrap gap-4 text-xs text-neutral-500">
        <span><span className="mr-1 inline-block h-0.5 w-5 bg-red-500 align-middle" />{referenceLabel}</span>
        <span><span className="mr-1 inline-block h-0.5 w-5 border-t-2 border-dashed border-violet-500 align-middle" />Model prediction</span>
        <span><span className="mr-1 inline-block size-3 bg-violet-500/30 align-middle" />Predicted risk region</span>
        {unc.available && <span>Shaded band: ensemble spread</span>}
      </div>
    </div>
  );
}
