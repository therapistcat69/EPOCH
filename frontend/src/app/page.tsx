"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { Loader2, Search } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { analyze, getRecent } from "@/lib/api";

export default function Home() {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const recent = useQuery({ queryKey: ["recent"], queryFn: getRecent });
  const run = useMutation({
    mutationFn: analyze,
    onSuccess: (r) => router.push(`/report/${r.analysis_id}`),
  });

  return (
    <main className="mx-auto w-full max-w-2xl px-4 py-16">
      <h1 className="text-4xl font-bold tracking-tight">Retention Predictor</h1>
      <p className="mt-2 text-lg text-neutral-500">Find the Drop-Off Before You Publish</p>

      <form
        className="mt-8 flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (url.trim()) run.mutate(url.trim());
        }}
      >
        <input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="Paste a YouTube video link  https://youtube.com/watch?v=..."
          className="min-w-0 flex-1 rounded-lg border border-neutral-400/40 bg-transparent px-3 py-2"
        />
        <button
          disabled={run.isPending}
          className="flex items-center gap-2 rounded-lg bg-red-600 px-4 py-2 font-medium text-white disabled:opacity-60"
        >
          {run.isPending ? <Loader2 className="size-4 animate-spin" /> : <Search className="size-4" />}
          Analyze Video
        </button>
      </form>
      <Link href="/login" className="mt-3 inline-block text-sm text-neutral-500 hover:underline">
        Connect YouTube to see your channel analytics →
      </Link>

      {run.isError && (
        <p role="alert" className="mt-4 rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-red-500">
          {run.error.message}
        </p>
      )}

      {recent.data && recent.data.length > 0 && (
        <section className="mt-12">
          <h2 className="mb-2 text-sm font-semibold uppercase text-neutral-500">Recent analyses</h2>
          <ul className="space-y-1">
            {recent.data.map((r) => (
              <li key={r.analysis_id}>
                <Link href={`/report/${r.analysis_id}`} className="hover:underline">
                  {r.title} <span className="text-neutral-500">· {r.channel_title}</span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}
