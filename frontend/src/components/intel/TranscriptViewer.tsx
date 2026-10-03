"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Upload } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { ErrorBox } from "@/components/dashboard/ui";
import { clock } from "@/lib/format";
import { intel, type DropOff, type Segment, type SegFeature } from "@/lib/intel-api";

type Props = {
  videoId: string;
  available: boolean;
  segments: Segment[];
  features: SegFeature[];
  drops: DropOff[];
  currentTimestamp: number | null;
  onSelect: (seconds: number) => void;
  riskRegions?: { start_seconds: number; end_seconds: number }[]; // ML-predicted risk (separate from observed drop-offs)
  estimated?: boolean;
  message?: string;
  onChanged: () => void;
};

export default function TranscriptViewer({ videoId, available, segments, features, drops, currentTimestamp, onSelect, riskRegions = [], estimated, message, onChanged }: Props) {
  const refs = useRef<Record<number, HTMLLIElement | null>>({});
  const feat = new Map(features.map((f) => [f.segment_id, f]));
  const active = currentTimestamp == null ? -1 : segments.findIndex((s) => currentTimestamp >= s.start_seconds && currentTimestamp < s.end_seconds);
  const idx = active >= 0 ? active : currentTimestamp == null ? -1 : segments.reduce((best, s, i) => (Math.abs(s.start_seconds - currentTimestamp) < Math.abs((segments[best]?.start_seconds ?? 1e9) - currentTimestamp) ? i : best), 0);

  useEffect(() => {
    if (idx >= 0) refs.current[idx]?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [idx]);

  if (!available) return <UploadPanel videoId={videoId} message={message} onDone={onChanged} />;
  const inDrop = (s: Segment) => drops.some((d) => d.from_seconds != null && d.to_seconds != null && s.end_seconds >= d.from_seconds && s.start_seconds <= d.to_seconds);
  const inRisk = (s: Segment) => riskRegions.some((r) => s.end_seconds >= r.start_seconds && s.start_seconds <= r.end_seconds);

  return (
    <div>
      {estimated && <p className="mb-2 rounded border border-yellow-500/40 bg-yellow-500/10 p-2 text-xs">Timestamps were estimated from the text length, so they are approximate.</p>}
      <ol className="max-h-96 space-y-1 overflow-y-auto pr-1 text-sm">
        {segments.map((s, i) => {
          const f = feat.get(s.segment_index);
          return (
            <li key={s.segment_index} ref={(el) => { refs.current[i] = el; }}>
              <button onClick={() => onSelect(s.start_seconds)} className={`w-full rounded-lg px-2 py-1 text-left hover:bg-neutral-400/10 ${i === idx ? "bg-violet-500/20 ring-1 ring-violet-500" : ""}`}>
                <span className="mr-2 font-mono text-xs text-neutral-500">{clock(s.start_seconds)}</span>
                {s.text}
                <span className="ml-1 inline-flex gap-1 align-middle">
                  {f?.is_hook && <Badge>hook</Badge>}
                  {f?.is_cta && <Badge>CTA</Badge>}
                  {f && f.repetition_score >= 0.55 && <Badge>repeats</Badge>}
                  {f?.topic_change && <Badge>topic shift</Badge>}
                  {inDrop(s) && <Badge tone="red">observed drop</Badge>}
                  {inRisk(s) && <Badge tone="violet">predicted risk</Badge>}
                </span>
                {f?.topic && <span className="block text-xs text-neutral-500">{f.topic}</span>}
              </button>
            </li>
          );
        })}
      </ol>
    </div>
  );

  function Badge({ children, tone }: { children: React.ReactNode; tone?: "red" | "violet" }) {
    const cls = tone === "red" ? "bg-red-500/20 text-red-500" : tone === "violet" ? "bg-violet-500/20 text-violet-500" : "bg-neutral-400/20";
    return <span className={`rounded px-1 text-[10px] ${cls}`}>{children}</span>;
  }
}

function UploadPanel({ videoId, message, onDone }: { videoId: string; message?: string; onDone: () => void }) {
  const qc = useQueryClient();
  const [text, setText] = useState("");
  const [format, setFormat] = useState<"txt" | "srt" | "vtt">("srt");
  const [language, setLanguage] = useState("");
  const done = () => {
    qc.invalidateQueries({ queryKey: ["video-report", videoId] });
    onDone();
  };
  const upload = useMutation({ mutationFn: () => intel.uploadTranscript(videoId, { format, content: text, language: language || undefined }), onSuccess: done });
  const audio = useMutation({ mutationFn: (f: File) => intel.transcribe(videoId, f, language || undefined), onSuccess: done });

  return (
    <div className="space-y-3 text-sm">
      <p className="font-medium">{message ?? "Transcript unavailable for this video."}</p>
      <p className="text-neutral-500">Upload a transcript (TXT, SRT or VTT) or an audio file to unlock hook, pacing, repetition and CTA analysis.</p>
      <div className="flex flex-wrap items-center gap-2">
        <select value={format} onChange={(e) => setFormat(e.target.value as "txt" | "srt" | "vtt")} className="rounded border border-neutral-400/40 bg-transparent px-2 py-1">
          {["srt", "vtt", "txt"].map((f) => <option key={f} value={f} className="text-black">{f.toUpperCase()}</option>)}
        </select>
        <select value={language} onChange={(e) => setLanguage(e.target.value)} className="rounded border border-neutral-400/40 bg-transparent px-2 py-1">
          <option value="" className="text-black">Auto-detect language</option>
          <option value="en" className="text-black">English</option>
          <option value="hi" className="text-black">Hindi</option>
        </select>
        <label className="flex cursor-pointer items-center gap-1 rounded border border-neutral-400/40 px-2 py-1">
          <Upload className="size-4" /> Upload Transcript
          <input type="file" accept=".txt,.srt,.vtt" className="hidden" onChange={async (e) => {
            const f = e.target.files?.[0];
            if (!f) return;
            const ext = f.name.split(".").pop()?.toLowerCase();
            if (ext === "srt" || ext === "vtt" || ext === "txt") setFormat(ext);
            setText(await f.text());
          }} />
        </label>
        <label className="flex cursor-pointer items-center gap-1 rounded border border-neutral-400/40 px-2 py-1">
          <Upload className="size-4" /> Upload Audio
          <input type="file" accept="audio/*,video/mp4,video/webm,.m4a,.mp3,.wav" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) audio.mutate(f); }} />
        </label>
      </div>
      <textarea value={text} onChange={(e) => setText(e.target.value)} placeholder="…or paste the transcript here" rows={5} className="w-full rounded border border-neutral-400/40 bg-transparent p-2 font-mono text-xs" />
      <button disabled={!text.trim() || upload.isPending} onClick={() => upload.mutate()} className="rounded bg-red-600 px-3 py-1.5 text-white disabled:opacity-50">
        {upload.isPending ? "Analyzing…" : "Analyze transcript"}
      </button>
      {audio.isPending && <p className="text-neutral-500">Transcribing audio with Groq Whisper…</p>}
      {(upload.error || audio.error) && <ErrorBox error={upload.error ?? audio.error} />}
    </div>
  );
}
