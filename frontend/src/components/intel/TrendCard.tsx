"use client";

import { compact } from "@/lib/format";
import type { Topic } from "@/lib/intel-api";

const TONE = { HIGH: "bg-green-500/20 text-green-500", MEDIUM: "bg-yellow-500/20 text-yellow-600", LOW: "bg-neutral-400/20 text-neutral-500" };

export default function TrendCard({ t }: { t: Topic }) {
  return (
    <article className="rounded-xl border border-neutral-400/30 p-4 text-sm">
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-lg font-semibold">{t.topic}</h3>
        <span className={`rounded px-2 py-0.5 text-xs font-semibold ${TONE[t.momentum_label]}`} title={`Content Momentum Index ${t.momentum_version}: ${t.momentum_score}`}>
          Momentum: {t.momentum_label}
        </span>
      </div>
      <dl className="mt-3 grid grid-cols-3 gap-2">
        <div><dt className="text-xs text-neutral-500">Videos analyzed</dt><dd className="font-semibold">{t.sample_size}</dd></div>
        <div><dt className="text-xs text-neutral-500">Median views</dt><dd className="font-semibold">{compact(t.median_views)}</dd></div>
        <div>
          <dt className="text-xs text-neutral-500">Newer vs older uploads</dt>
          <dd className="font-semibold">{t.recent_growth == null ? "Data unavailable" : `${t.recent_growth >= 0 ? "+" : ""}${(t.recent_growth * 100).toFixed(0)}%`}</dd>
        </div>
      </dl>
      <p className="mt-1 text-[11px] text-neutral-500">Views/day of the newest third of uploads vs older ones in this sample. Momentum = RetainAI Content Momentum Index {t.momentum_version}.</p>
      <div className="mt-3 grid gap-3 md:grid-cols-2">
        <div>
          <h4 className="text-xs font-semibold uppercase text-neutral-500">Common formats</h4>
          <ul className="list-disc pl-5">{t.common_formats.length ? t.common_formats.map((f) => <li key={f.format}>{f.format}</li>) : <li className="list-none text-neutral-500">Data unavailable</li>}</ul>
        </div>
        <div>
          <h4 className="text-xs font-semibold uppercase text-neutral-500">Common title patterns</h4>
          <ul className="list-disc pl-5">{t.common_title_patterns.length ? t.common_title_patterns.map((p) => <li key={p.pattern}>{p.pattern}</li>) : <li className="list-none text-neutral-500">Data unavailable</li>}</ul>
        </div>
      </div>
      {t.top_channels.length > 0 && <p className="mt-2 text-xs text-neutral-500">Channels in sample: {t.top_channels.join(", ")}</p>}
      <details className="mt-2">
        <summary className="cursor-pointer text-xs text-neutral-500">Example videos</summary>
        <ul className="mt-1 space-y-0.5 text-xs">
          {t.example_videos.map((v) => <li key={v.video_id}><a className="underline" href={`https://www.youtube.com/watch?v=${v.video_id}`} target="_blank" rel="noreferrer">{v.title}</a> · {compact(v.views)} views</li>)}
        </ul>
      </details>
    </article>
  );
}
