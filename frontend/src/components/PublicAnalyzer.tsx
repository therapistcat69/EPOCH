"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { Loader2, Search } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import ModelProvenance from "@/components/ml/ModelProvenance";
import TranscriptAnalyzer from "@/components/ml/TranscriptAnalyzer";
import { analyze, getRecent } from "@/lib/api";

/** Public (no-login) analysis workflow: paste a YouTube URL or any transcript. Shown below the landing hero. */
export default function PublicAnalyzer() {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const recent = useQuery({ queryKey: ["recent"], queryFn: getRecent });
  const run = useMutation({ mutationFn: analyze, onSuccess: (r) => router.push(`/report/${r.analysis_id}`) });

  return (
    <section id="analyze" className="w-full bg-black px-4 py-16 text-slate-100">
      <div className="mx-auto w-full max-w-4xl">
        <h2 className="text-2xl font-bold tracking-tight">Analyze a video</h2>
        <p className="mt-1 text-neutral-400">Paste a public YouTube link, or analyze any transcript below. No login needed.</p>

        <form className="mt-6 flex gap-2" onSubmit={(e) => { e.preventDefault(); if (url.trim()) run.mutate(url.trim()); }}>
          <input
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="Paste a YouTube video link  https://youtube.com/watch?v=..."
            className="min-w-0 flex-1 rounded-lg border border-white/15 bg-transparent px-3 py-2"
          />
          <button disabled={run.isPending} className="flex items-center gap-2 rounded-lg bg-red-600 px-4 py-2 font-medium text-white disabled:opacity-60">
            {run.isPending ? <Loader2 className="size-4 animate-spin" /> : <Search className="size-4" />}
            Analyze Video
          </button>
        </form>
        <div className="mt-3 flex flex-wrap gap-4 text-sm text-neutral-400">
          <Link href="/trends" className="hover:underline">Trend Radar →</Link>
          <Link href="/benchmark" className="hover:underline">Genre benchmark →</Link>
          <Link href="/models" className="hover:underline">Model status →</Link>
        </div>
        <div className="mt-3"><ModelProvenance /></div>

        {run.isError && <p role="alert" className="mt-4 rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-red-500">{run.error.message}</p>}

        <TranscriptAnalyzer />

        {recent.data && recent.data.length > 0 && (
          <section className="mt-12">
            <h3 className="mb-2 text-sm font-semibold uppercase text-neutral-400">Recent analyses</h3>
            <ul className="space-y-1">
              {recent.data.map((r) => (
                <li key={r.analysis_id}>
                  <Link href={`/report/${r.analysis_id}`} className="hover:underline">
                    {r.title} <span className="text-neutral-400">· {r.channel_title}</span>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </section>
  );
}
