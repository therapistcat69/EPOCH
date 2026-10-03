"use client";

import { clock } from "@/lib/format";
import type { MlExplanation, RiskRegion } from "@/lib/ml-api";

/** Predicted risk regions with MODEL-BASED explanations (attributions, not causal reasons). Click to jump the transcript. */
export default function RiskRegions({ regions, onSelect, groq }: { regions: RiskRegion[]; onSelect: (seconds: number) => void; groq?: MlExplanation }) {
  if (regions.length === 0) return <p className="text-sm text-neutral-500">The model found no elevated-risk regions.</p>;
  const ai = groq?.available ? groq.report?.risk_explanations ?? [] : [];
  return (
    <div className="space-y-3">
      {regions.map((r, i) => {
        const g = ai.find((e) => Math.abs(e.start_seconds - r.start_seconds) < 0.2 && Math.abs(e.end_seconds - r.end_seconds) < 0.2);
        return (
          <div key={i} className="rounded-lg border border-violet-500/40 bg-violet-500/5 p-3 text-sm">
            <button onClick={() => onSelect(r.start_seconds)} className="font-semibold underline">
              {clock(r.start_seconds)}–{clock(r.end_seconds)}
            </button>
            <span className="ml-2 text-neutral-500">Potential retention risk · risk score {r.risk_score.toFixed(2)} · predicted drop {r.predicted_drop.toFixed(1)} pts</span>
            {r.factors.length > 0 && (
              <>
                <p className="mt-2 text-xs font-semibold uppercase text-neutral-500">Top model features (model-based explanation)</p>
                <ol className="list-decimal pl-5">{r.factors.map((f) => <li key={f.feature}>{f.label}</li>)}</ol>
              </>
            )}
            <p className="mt-1 text-neutral-500">{r.explanation}</p>
            {g && (
              <div className="mt-2 rounded border border-neutral-400/30 p-2">
                <p><b>What is happening:</b> {g.what_is_happening}</p>
                <p className="text-neutral-500"><b>Possible editorial experiment:</b> {g.possible_experiment}</p>
              </div>
            )}
          </div>
        );
      })}
      {groq && !groq.available && <p className="text-xs text-neutral-500">{groq.message}</p>}
      {groq?.available && groq.report && <p className="rounded border border-neutral-400/30 p-2 text-sm">{groq.report.summary}</p>}
    </div>
  );
}
