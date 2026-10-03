"use client";

import { useQuery } from "@tanstack/react-query";
import { Sparkles } from "lucide-react";
import { useState } from "react";
import { Card, ErrorBox, Loading } from "@/components/dashboard/ui";
import { ml } from "@/lib/ml-api";
import ModelBanner from "./ModelBanner";
import ModelProvenance from "./ModelProvenance";
import PredictionChart from "./PredictionChart";
import RiskRegions from "./RiskRegions";

export function useVideoPrediction(videoId: string, includeAi = false) {
  return useQuery({ queryKey: ["prediction", videoId, includeAi], queryFn: () => ml.videoPrediction(videoId, includeAi), retry: false });
}

/** PREDICTED RETENTION for a creator's video. The "Actual" line appears only when real YouTube Analytics retention exists. */
export default function PredictedRetention({ videoId, currentTimestamp, onSelect }: { videoId: string; currentTimestamp: number | null; onSelect: (s: number) => void }) {
  const [ai, setAi] = useState(false);
  const status = useQuery({ queryKey: ["ml-status"], queryFn: ml.status, refetchInterval: (q) => (q.state.data?.state === "loading" ? 4000 : false) });
  const q = useVideoPrediction(videoId, ai);

  return (
    <Card title="Predicted retention" right={<span className="text-xs text-neutral-500">ML model · predicted, not observed</span>}>
      {status.data && !status.data.model_available && status.data.state !== "loading" && (
        <p className="rounded-lg border border-dashed border-neutral-400/50 p-4 text-sm text-neutral-500">ML model not connected. {status.data.message}</p>
      )}
      {status.data?.state === "loading" && <Loading label="The ML model is loading (first start takes about a minute)…" />}
      {status.data?.model_available && (
        <>
          {q.isLoading && <Loading label="Predicting retention…" />}
          {q.error && <ErrorBox error={q.error} />}
          {q.data && !q.data.available && (
            <p className="rounded-lg border border-dashed border-neutral-400/50 p-4 text-sm text-neutral-500">{q.data.message} Upload a transcript or audio above to get a prediction.</p>
          )}
          {q.data?.available && (
            <div className="space-y-4">
              <ModelBanner p={q.data.prediction} />
              <ModelProvenance />
              <PredictionChart
                prediction={q.data.prediction}
                reference={q.data.actual.available ? q.data.actual.points.map((p) => ({ time_ratio: p.time_ratio, value: p.value })) : undefined}
                referenceLabel="Actual YouTube retention"
                currentTimestamp={currentTimestamp}
                onSelect={onSelect}
              />
              {!q.data.actual.available && <p className="text-xs text-neutral-500">{q.data.actual.note} Only the model prediction is shown.</p>}
              {q.data.prediction.uncertainty.available ? (
                <p className="text-xs text-neutral-500">Uncertainty: {q.data.prediction.uncertainty.note}</p>
              ) : (
                <p className="text-xs text-neutral-500">Uncertainty estimate unavailable.</p>
              )}
              <div className="flex items-center justify-between">
                <h3 className="font-semibold">Potential retention-risk regions</h3>
                <button onClick={() => setAi(true)} disabled={ai} className="flex items-center gap-1 rounded-lg border border-neutral-400/40 px-3 py-1.5 text-sm disabled:opacity-50">
                  <Sparkles className="size-4" /> {ai ? "AI explanation on" : "Explain with AI"}
                </button>
              </div>
              <RiskRegions regions={q.data.prediction.risk_segments} onSelect={onSelect} groq={q.data.groq} />
            </div>
          )}
        </>
      )}
    </Card>
  );
}
