"use client";
/* eslint-disable @next/next/no-img-element */

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { X } from "lucide-react";
import { useState } from "react";
import { api, type OwnedVideo, type Range } from "@/lib/creator-api";
import { clock, compact, hours, pct, shortDate } from "@/lib/format";
import { Card, Empty, ErrorBox, Loading, Stat } from "./ui";

const SORTS: [string, string][] = [
  ["newest", "Newest"], ["oldest", "Oldest"], ["views", "Most Views"], ["highest_avp", "Highest Avg View %"],
  ["lowest_avp", "Lowest Avg View %"], ["longest", "Longest"], ["shortest", "Shortest"],
];

export default function Videos({ range, onOpenRetention }: { range: Range; onOpenRetention: (v: OwnedVideo) => void }) {
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState("newest");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<OwnedVideo | null>(null);
  const limit = 15;
  const q = useQuery({
    queryKey: ["videos", range, page, sort, search],
    queryFn: () => api.videos(range, { page, limit, sort, search }),
    placeholderData: keepPreviousData,
  });
  const pages = q.data ? Math.max(1, Math.ceil(q.data.total / limit)) : 1;

  return (
    <div className="space-y-4">
      <Card
        title="Your Videos"
        right={
          <div className="flex gap-2">
            <input value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} placeholder="Search videos" className="rounded-lg border border-neutral-400/40 bg-transparent px-2 py-1 text-sm" />
            <select value={sort} onChange={(e) => { setSort(e.target.value); setPage(1); }} className="rounded-lg border border-neutral-400/40 bg-transparent px-2 py-1 text-sm">
              {SORTS.map(([v, l]) => <option key={v} value={v} className="text-black">{l}</option>)}
            </select>
          </div>
        }
      >
        {q.isLoading && <Loading />}
        {q.error && <ErrorBox error={q.error} />}
        {q.data && q.data.total === 0 && <Empty>No videos found. Click “Sync YouTube Data” to load your library.</Empty>}
        {q.data && q.data.total > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[900px] text-sm">
              <thead className="text-left text-xs uppercase text-neutral-500">
                <tr>
                  <th></th><th>Title</th><th>Published</th><th>Duration</th><th>Views</th><th>Watch time</th>
                  <th>Avg duration</th><th>Avg view %</th><th>Likes</th><th>Comments</th><th>Subs +</th>
                </tr>
              </thead>
              <tbody>
                {q.data.items.map(({ video: v, metrics: m }) => (
                  <tr key={v.video_id} onClick={() => setSelected(v)} className="cursor-pointer border-t border-neutral-400/20 hover:bg-neutral-400/10">
                    <td className="py-1 pr-2">{v.thumbnail_url && <img src={v.thumbnail_url} alt="" className="h-9 rounded" />}</td>
                    <td className="max-w-xs truncate pr-2">
                      {v.title} {v.privacy_status && v.privacy_status !== "public" && <span className="ml-1 rounded bg-neutral-400/20 px-1 text-xs">{v.privacy_status}</span>}
                    </td>
                    <td>{shortDate(v.published_at)}</td>
                    <td>{clock(v.duration_seconds)}</td>
                    <td>{compact(m?.views)}</td>
                    <td>{hours(m?.watch_time_minutes)}</td>
                    <td>{m?.average_view_duration_seconds == null ? "—" : clock(m.average_view_duration_seconds)}</td>
                    <td>{pct(m?.average_view_percentage)}</td>
                    <td>{compact(m?.likes)}</td>
                    <td>{compact(m?.comments)}</td>
                    <td>{compact(m?.subscribers_gained)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {q.data && q.data.total > 0 && (
          <div className="mt-3 flex items-center justify-between text-sm">
            <span className="text-neutral-500">{q.data.total} videos · “—” means YouTube returned no analytics for the date range</span>
            <div className="flex items-center gap-2">
              <button disabled={page <= 1} onClick={() => setPage(page - 1)} className="rounded border border-neutral-400/40 px-2 py-1 disabled:opacity-40">Prev</button>
              <span>{page} / {pages}</span>
              <button disabled={page >= pages} onClick={() => setPage(page + 1)} className="rounded border border-neutral-400/40 px-2 py-1 disabled:opacity-40">Next</button>
            </div>
          </div>
        )}
      </Card>

      {q.data && (
        <Card title="Channel insights (descriptive)">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
            <Stat label="Videos analyzed" value={String(q.data.insights.videos_analyzed)} sub={`${range.start} → ${range.end}`} />
            <Stat label="Avg view %" value={pct(q.data.insights.average_view_percentage)} />
            <Stat label="Median view %" value={pct(q.data.insights.median_view_percentage)} />
            <Stat label="Avg view duration" value={clock(q.data.insights.average_view_duration_seconds)} />
            <Stat label="Median view duration" value={clock(q.data.insights.median_view_duration_seconds)} />
          </div>
        </Card>
      )}

      {selected && <Drawer video={selected} range={range} onClose={() => setSelected(null)} onRetention={() => onOpenRetention(selected)} />}
    </div>
  );
}

function Drawer({ video, range, onClose, onRetention }: { video: OwnedVideo; range: Range; onClose: () => void; onRetention: () => void }) {
  const d = useQuery({ queryKey: ["video", video.video_id, range], queryFn: () => api.videoDetail(video.video_id, range) });
  const m = d.data?.metrics;
  return (
    <aside className="fixed inset-y-0 right-0 z-20 w-full max-w-md overflow-y-auto border-l border-neutral-400/30 bg-[var(--background)] p-5 shadow-2xl">
      <button onClick={onClose} aria-label="Close" className="float-right"><X className="size-5" /></button>
      {video.thumbnail_url && <img src={video.thumbnail_url} alt="" className="mb-3 w-full rounded-lg" />}
      <h3 className="text-lg font-semibold">{video.title}</h3>
      <p className="text-sm text-neutral-500">{clock(video.duration_seconds)} · {shortDate(video.published_at)}</p>
      {d.isLoading && <Loading />}
      {d.error && <ErrorBox error={d.error} />}
      {m && (
        <div className="mt-4 grid grid-cols-2 gap-3">
          <Stat label="Views" value={compact(m.views)} />
          <Stat label="Watch time" value={hours(m.watch_time_minutes)} />
          <Stat label="Avg view duration" value={m.average_view_duration_seconds == null ? "—" : clock(m.average_view_duration_seconds)} />
          <Stat label="Avg view %" value={pct(m.average_view_percentage)} />
          <Stat label="Likes" value={compact(m.likes)} />
          <Stat label="Comments" value={compact(m.comments)} />
          <Stat label="Subs gained" value={compact(m.subscribers_gained)} />
          <Stat label="Subs lost" value={compact(m.subscribers_lost)} />
        </div>
      )}
      <button onClick={onRetention} className="mt-5 w-full rounded-lg bg-red-600 py-2 font-medium text-white">View audience retention</button>
    </aside>
  );
}
