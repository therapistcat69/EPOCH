"use client";

import { useMutation } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useState } from "react";
import { Card, ErrorBox } from "@/components/dashboard/ui";
import { clock } from "@/lib/format";
import { ml } from "@/lib/ml-api";
import ModelBanner from "./ModelBanner";
import PredictionChart from "./PredictionChart";
import RiskRegions from "./RiskRegions";

/** Paste/upload ANY transcript (TXT/SRT/VTT) -> same inference pipeline -> predicted curve, risk regions, explanations. */
export default function TranscriptAnalyzer() {
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [fmt, setFmt] = useState<"txt" | "srt" | "vtt">("txt");
  const [t, setT] = useState<number | null>(null);
  const run = useMutation({ mutationFn: ml.predictText });
  const d = run.data;
  const active = d && t != null ? d.transcript.segments.findIndex((s) => t >= s.start && t < s.end) : -1;

  const onFile = async (f?: File) => {
    if (!f) return;
    setContent(await f.text());
    const ext = f.name.split(".").pop()?.toLowerCase();
    if (ext === "srt" || ext === "vtt" || ext === "txt") setFmt(ext);
  };

  return (
    <section className="mt-10 space-y-4">
      <h2 className="text-sm font-semibold uppercase text-neutral-500">Or analyze a transcript</h2>
      <form className="space-y-2" onSubmit={(e) => { e.preventDefault(); setT(null); if (content.trim()) run.mutate({ title, format: fmt, content }); }}>
        <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Video title (optional, used for title/content alignment)" className="w-full rounded-lg border border-neutral-400/40 bg-transparent px-3 py-2" />
        <textarea value={content} onChange={(e) => setContent(e.target.value)} rows={6} placeholder="Paste a transcript here (TXT with 0:15 timestamps, SRT or VTT)…" className="w-full rounded-lg border border-neutral-400/40 bg-transparent px-3 py-2 font-mono text-sm" />
        <div className="flex flex-wrap items-center gap-3">
          <select value={fmt} onChange={(e) => setFmt(e.target.value as "txt" | "srt" | "vtt")} className="rounded-lg border border-neutral-400/40 bg-transparent px-2 py-2 text-sm">
            <option value="txt" className="text-black">TXT</option><option value="srt" className="text-black">SRT</option><option value="vtt" className="text-black">VTT</option>
          </select>
          <input type="file" accept=".txt,.srt,.vtt" onChange={(e) => onFile(e.target.files?.[0])} className="text-sm" />
          <button disabled={run.isPending || !content.trim()} className="ml-auto flex items-center gap-2 rounded-lg bg-red-600 px-4 py-2 font-medium text-white disabled:opacity-60">
            {run.isPending && <Loader2 className="size-4 animate-spin" />} Predict retention
          </button>
        </div>
      </form>
      {run.isError && <ErrorBox error={run.error} />}
      {d && (
        <div className="space-y-4">
          <ModelBanner p={d.prediction} />
          <Card title="Predicted retention" right={<span className="text-xs text-neutral-500">predicted, not observed</span>}>
            <PredictionChart prediction={d.prediction} referenceLabel="" currentTimestamp={t} onSelect={setT} />
            {d.transcript.timestamps_estimated && <p className="mt-2 text-xs text-yellow-600">Timestamps were estimated from the text (no timestamps in the upload), so positions are approximate.</p>}
          </Card>
          <div className="grid gap-4 lg:grid-cols-2">
            <Card title="Transcript">
              <ol className="max-h-96 space-y-1 overflow-y-auto pr-1 text-sm">
                {d.transcript.segments.map((s, i) => (
                  <li key={s.segment_id}>
                    <button onClick={() => setT(s.start)} className={`w-full rounded-lg px-2 py-1 text-left hover:bg-neutral-400/10 ${i === active ? "bg-amber-500/20 ring-1 ring-amber-500" : ""}`}>
                      <span className="mr-2 font-mono text-xs text-neutral-500">{clock(s.start)}</span>{s.text}
                    </button>
                  </li>
                ))}
              </ol>
            </Card>
            <Card title="Potential retention-risk regions"><RiskRegions regions={d.prediction.risk_segments} onSelect={setT} /></Card>
          </div>
        </div>
      )}
    </section>
  );
}
