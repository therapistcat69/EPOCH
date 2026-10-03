"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { ChevronRight, Loader2, Search } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import ModelProvenance from "@/components/ml/ModelProvenance";
import TranscriptAnalyzer from "@/components/ml/TranscriptAnalyzer";
import { analyze, getRecent } from "@/lib/api";
import RetainLoadingState from "@/components/RetainLoadingState";

/** Public (no-login) analysis workflow: paste a YouTube URL or any transcript. Shown below the landing hero. */
export default function PublicAnalyzer() {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [showAll, setShowAll] = useState(false);
  const recent = useQuery({ queryKey: ["recent"], queryFn: getRecent });
  const run = useMutation({ mutationFn: analyze, onSuccess: (r) => router.push(`/report/${r.analysis_id}`) });

  const visibleRecent = showAll ? recent.data : recent.data?.slice(0, 5);

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
          <button disabled={run.isPending} className="flex items-center gap-2 rounded-lg bg-red-600 px-4 py-2 font-medium text-white disabled:opacity-60 transition-opacity">
            {run.isPending ? <Loader2 className="size-4 animate-spin" /> : <Search className="size-4" />}
            {run.isPending ? "Analyzing…" : "Analyze Video"}
          </button>
        </form>
        <div className="mt-3 flex flex-wrap gap-4 text-sm text-neutral-400">
          <Link href="/trends" className="hover:underline">Trend Radar →</Link>
          <Link href="/benchmark" className="hover:underline">Genre benchmark →</Link>
          <Link href="/models" className="hover:underline">Model status →</Link>
        </div>
        <div className="mt-3"><ModelProvenance /></div>

        {run.isPending && (
          <div className="mt-8 rounded-2xl border border-white/[0.08] bg-[#09090d]/80 p-6 sm:p-8 backdrop-blur-xl shadow-2xl">
            <RetainLoadingState
              title="Analyzing your video"
              subtitle="Processing video signals..."
              minHeight="min-h-[220px]"
            />
          </div>
        )}

        {run.isError && <p role="alert" className="mt-4 rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-red-500">{run.error.message}</p>}

        <TranscriptAnalyzer />

        {recent.data && recent.data.length > 0 && (
          <section className="mt-12">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-[12px] sm:text-[13px] font-semibold tracking-[0.1em] text-white/65 uppercase">
                RECENT ANALYSES
              </h3>
              {recent.data.length > 5 && (
                <button
                  type="button"
                  onClick={() => setShowAll((prev) => !prev)}
                  className="text-[12px] font-medium text-neutral-400 hover:text-white transition-colors duration-150"
                >
                  {showAll ? "Show less" : `View all (${recent.data.length})`}
                </button>
              )}
            </div>

            <div className="overflow-hidden rounded-[13px] border border-white/[0.08] bg-white/[0.02]">
              <div className="divide-y divide-white/[0.08]">
                {visibleRecent?.map((r) => (
                  <Link
                    key={r.analysis_id}
                    href={`/report/${r.analysis_id}`}
                    className="group flex items-center justify-between gap-4 px-4 py-3.5 sm:px-5 transition-colors duration-200 ease-out hover:bg-white/[0.05]"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[15px] font-medium text-white/90 transition-colors duration-200 ease-out group-hover:text-white">
                        {r.title}
                      </p>
                      {r.channel_title && (
                        <p className="mt-0.5 truncate text-[12px] sm:text-[13px] text-neutral-400 transition-colors duration-200 ease-out group-hover:text-neutral-300">
                          {r.channel_title}
                        </p>
                      )}
                    </div>
                    <ChevronRight className="size-4 shrink-0 text-white/35 transition-all duration-200 ease-out group-hover:translate-x-[3px] group-hover:text-white/85" />
                  </Link>
                ))}
              </div>
            </div>
          </section>
        )}
      </div>
    </section>
  );
}
