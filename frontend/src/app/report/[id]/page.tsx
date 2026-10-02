"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { getReport } from "@/lib/api";

const n = (v: number | null | undefined) => (v == null ? "—" : new Intl.NumberFormat("en", { notation: "compact" }).format(v));

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-neutral-400/30 p-3">
      <div className="text-xs uppercase text-neutral-500">{label}</div>
      <div className="text-xl font-semibold">{value}</div>
    </div>
  );
}

export default function ReportPage() {
  const { id } = useParams<{ id: string }>();
  const { data, isLoading, error } = useQuery({ queryKey: ["report", id], queryFn: () => getReport(id) });

  return (
    <main className="mx-auto w-full max-w-3xl space-y-6 px-4 py-10">
      <Link href="/" className="flex items-center gap-1 text-sm text-neutral-500 hover:underline">
        <ArrowLeft className="size-4" /> New analysis
      </Link>

      {isLoading && <p>Loading report…</p>}
      {error && <p role="alert" className="rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-red-500">{error.message}</p>}

      {data && (
        <>
          <section className="flex gap-4">
            {data.video.thumbnail_url && (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={data.video.thumbnail_url} alt="" className="h-24 rounded-lg" />
            )}
            <div>
              <h1 className="text-2xl font-bold">{data.video.title}</h1>
              <p className="text-neutral-500">
                {data.video.channel.title} · {data.video.published_at?.slice(0, 10)} · {data.video.duration_formatted} ·{" "}
                {data.video.category_name ?? "Uncategorised"}
              </p>
            </div>
          </section>

          <section className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat label="Views" value={n(data.video.statistics.views)} />
            <Stat label="Likes" value={n(data.video.statistics.likes)} />
            <Stat label="Comments" value={n(data.video.statistics.comments)} />
            <Stat label="Duration" value={data.video.duration_formatted} />
          </section>

          {data.channel && (
            <section>
              <h2 className="mb-2 font-semibold">Channel snapshot</h2>
              <div className="grid grid-cols-3 gap-3">
                <Stat label="Subscribers" value={n(data.channel.subscriber_count)} />
                <Stat label="Channel views" value={n(data.channel.total_views)} />
                <Stat label="Videos" value={n(data.channel.video_count)} />
              </div>
            </section>
          )}

          <section>
            <h2 className="mb-2 font-semibold">ML feature readiness</h2>
            <ul className="text-sm">
              {Object.entries(data.feature_readiness).map(([k, s]) => (
                <li key={k} className="flex justify-between border-b border-neutral-400/20 py-1">
                  <span className="font-mono">{k}</span>
                  <span className={s === "available" ? "text-green-500" : "text-neutral-500"}>
                    {s === "available" ? "available" : "pending pipeline"}
                  </span>
                </li>
              ))}
            </ul>
          </section>

          <section className="rounded-lg border border-dashed border-neutral-400/50 p-6">
            <h2 className="font-semibold">Retention Intelligence</h2>
            <p className="mt-1 text-neutral-500">
              ML model not connected yet. The YouTube data has been normalized and the feature payload is ready for the
              prediction pipeline.
            </p>
            <div className="mt-4 flex h-32 items-center justify-center rounded bg-neutral-400/10 text-sm text-neutral-500">
              Predicted Retention Curve — coming from ML pipeline
            </div>
          </section>

          <p className="text-xs text-neutral-500">
            Source: {data.source}
            {data.cached ? " · cached" : ""}
          </p>
        </>
      )}
    </main>
  );
}
