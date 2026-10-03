"use client";

import type { Prediction } from "@/lib/ml-api";

/** Always shows what the model was trained on. Synthetic-trained models are labelled DEVELOPMENT / SYNTHETIC DATA. */
export default function ModelBanner({ p }: { p: Pick<Prediction, "trained_on" | "model_name" | "model_version" | "data_mode_warning" | "embedding_model" | "segment_seconds"> }) {
  const synthetic = p.trained_on.includes("synthetic");
  return (
    <div className={`rounded-lg border p-3 text-sm ${synthetic ? "border-yellow-500/50 bg-yellow-500/10" : "border-green-500/40 bg-green-500/10"}`}>
      {synthetic && <p className="text-xs font-bold tracking-widest text-yellow-600">DEVELOPMENT / SYNTHETIC DATA</p>}
      <p>
        Model: <b>{p.model_name}</b> {p.model_version} · trained on <b>{p.trained_on}</b> data · {p.segment_seconds}s segments · embeddings {p.embedding_model}
      </p>
      {p.data_mode_warning && <p className="mt-1 text-neutral-500">{p.data_mode_warning}</p>}
    </div>
  );
}
