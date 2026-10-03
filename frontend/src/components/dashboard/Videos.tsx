"use client";
/* eslint-disable @next/next/no-img-element */

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ArrowRight, Clock, Eye, Film, Search, X } from "lucide-react";
import { useState } from "react";
import { api, type OwnedVideo, type Range } from "@/lib/creator-api";
import type { CreatorPalette } from "@/lib/creatorTheme";
import { clock, compact, hours, pct, shortDate } from "@/lib/format";
import { Card, Empty, ErrorBox, Loading, Stat } from "./ui";

const SORTS: [string, string][] = [
  ["newest", "Newest Uploads"],
  ["oldest", "Oldest Uploads"],
  ["views", "Most Views"],
  ["highest_avp", "Highest Retention (Avg View %)"],
  ["lowest_avp", "Lowest Retention (Avg View %)"],
  ["longest", "Longest Duration"],
  ["shortest", "Shortest Duration"],
];

interface VideosProps {
  range: Range;
  onOpenRetention: (v: OwnedVideo) => void;
  creatorTheme?: CreatorPalette;
}

export default function Videos({ range, onOpenRetention, creatorTheme }: VideosProps) {
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
  const primaryAccent = creatorTheme?.primary ?? "#67E8F9";

  return (
    <div className="space-y-6">
      <Card
        title="Your Video Library"
        right={
          <div className="flex flex-wrap items-center gap-2.5">
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 size-3.5 text-neutral-500" />
              <input
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setPage(1);
                }}
                placeholder="Search videos..."
                className="w-48 sm:w-60 rounded-xl border border-white/10 bg-white/[0.03] pl-8 pr-3 py-1.5 text-xs text-white placeholder-neutral-500 focus:border-white/25 focus:outline-none transition-colors"
              />
            </div>
            <select
              value={sort}
              onChange={(e) => {
                setSort(e.target.value);
                setPage(1);
              }}
              className="rounded-xl border border-white/10 bg-[#0c0d14] px-3 py-1.5 text-xs text-white focus:border-white/25 focus:outline-none"
            >
              {SORTS.map(([v, l]) => (
                <option key={v} value={v} className="bg-neutral-900 text-white">
                  {l}
                </option>
              ))}
            </select>
          </div>
        }
      >
        {q.isLoading && <Loading label="Loading video performance library…" />}
        {q.error && <ErrorBox error={q.error} />}
        {q.data && q.data.total === 0 && (
          <Empty>No videos found matching your filter. Click “Sync YouTube Data” to refresh your library.</Empty>
        )}

        {q.data && q.data.total > 0 && (
          <div className="space-y-4">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[850px] text-xs">
                <thead className="border-b border-white/[0.08] text-left uppercase text-neutral-400 font-mono tracking-wider">
                  <tr>
                    <th className="py-2.5 pr-2 w-16">Preview</th>
                    <th className="py-2.5 pr-4">Video Details</th>
                    <th className="py-2.5 pr-4">Published</th>
                    <th className="py-2.5 pr-4">Duration</th>
                    <th className="py-2.5 pr-4">Views</th>
                    <th className="py-2.5 pr-4">Watch Time</th>
                    <th className="py-2.5 pr-4">Retention %</th>
                    <th className="py-2.5 pr-4">Likes</th>
                    <th className="py-2.5">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/[0.04]">
                  {q.data.items.map(({ video: v, metrics: m }) => (
                    <tr
                      key={v.video_id}
                      onClick={() => setSelected(v)}
                      className="group cursor-pointer hover:bg-white/[0.03] transition-colors"
                    >
                      <td className="py-2 pr-2">
                        {v.thumbnail_url ? (
                          <div className="relative size-12 rounded-lg overflow-hidden border border-white/10 shrink-0">
                            <img src={v.thumbnail_url} alt="" className="size-full object-cover group-hover:scale-105 transition-transform" />
                          </div>
                        ) : (
                          <div className="size-12 rounded-lg bg-neutral-900 border border-white/10 flex items-center justify-center text-neutral-600">
                            <Film className="size-5" />
                          </div>
                        )}
                      </td>
                      <td className="py-2 pr-4 max-w-xs">
                        <div className="font-semibold text-white group-hover:text-neutral-200 transition-colors truncate">
                          {v.title}
                        </div>
                        {v.privacy_status && v.privacy_status !== "public" && (
                          <span className="inline-block mt-0.5 rounded bg-white/10 px-1.5 py-0.2 text-[10px] text-neutral-400 uppercase font-mono">
                            {v.privacy_status}
                          </span>
                        )}
                      </td>
                      <td className="py-2 pr-4 text-neutral-400 font-mono">{shortDate(v.published_at)}</td>
                      <td className="py-2 pr-4 text-neutral-400 font-mono">{clock(v.duration_seconds)}</td>
                      <td className="py-2 pr-4 font-bold text-white">{compact(m?.views)}</td>
                      <td className="py-2 pr-4 text-neutral-300">{hours(m?.watch_time_minutes)}</td>
                      <td className="py-2 pr-4">
                        {m?.average_view_percentage != null ? (
                          <span
                            className="font-bold font-mono px-2 py-0.5 rounded"
                            style={{ backgroundColor: `${primaryAccent}15`, color: primaryAccent }}
                          >
                            {pct(m.average_view_percentage)}
                          </span>
                        ) : (
                          <span className="text-neutral-500">—</span>
                        )}
                      </td>
                      <td className="py-2 pr-4 text-neutral-400">{compact(m?.likes)}</td>
                      <td className="py-2">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            onOpenRetention(v);
                          }}
                          className="inline-flex items-center gap-1 rounded-lg border border-white/10 bg-white/[0.02] hover:bg-white/[0.08] px-2.5 py-1 text-[11px] font-medium text-neutral-300 hover:text-white transition-all"
                        >
                          Retention <ArrowRight className="size-3 text-[#ff1f3d]" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination Controls */}
            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-white/[0.06] pt-3 text-xs">
              <span className="text-neutral-500 font-mono">
                {q.data.total} total videos in library
              </span>
              <div className="flex items-center gap-2">
                <button
                  disabled={page <= 1}
                  onClick={() => setPage((p) => p - 1)}
                  className="rounded-lg border border-white/10 bg-white/[0.02] px-3 py-1 text-xs text-neutral-300 hover:text-white disabled:opacity-30 disabled:pointer-events-none transition-colors"
                >
                  Previous
                </button>
                <span className="font-mono text-neutral-400 px-1">
                  {page} / {pages}
                </span>
                <button
                  disabled={page >= pages}
                  onClick={() => setPage((p) => p + 1)}
                  className="rounded-lg border border-white/10 bg-white/[0.02] px-3 py-1 text-xs text-neutral-300 hover:text-white disabled:opacity-30 disabled:pointer-events-none transition-colors"
                >
                  Next
                </button>
              </div>
            </div>
          </div>
        )}
      </Card>

      {/* Aggregate Descriptive Insights */}
      {q.data && (
        <Card title="Library Baseline Retention">
          <div className="grid grid-cols-2 gap-3 sm:gap-4 md:grid-cols-5">
            <Stat
              label="Videos Analyzed"
              value={String(q.data.insights.videos_analyzed)}
              sub={`${range.start} → ${range.end}`}
              icon={<Film className="size-4" />}
            />
            <Stat
              label="Avg Retention %"
              value={pct(q.data.insights.average_view_percentage)}
              accentColor={primaryAccent}
            />
            <Stat
              label="Median Retention %"
              value={pct(q.data.insights.median_view_percentage)}
              accentColor="#38BDF8"
            />
            <Stat
              label="Avg View Duration"
              value={clock(q.data.insights.average_view_duration_seconds)}
              accentColor="#C4B5FD"
            />
            <Stat
              label="Median Duration"
              value={clock(q.data.insights.median_view_duration_seconds)}
              accentColor="#86EFAC"
            />
          </div>
        </Card>
      )}

      {/* Video Detail Slide-Over Drawer */}
      {selected && (
        <Drawer
          video={selected}
          range={range}
          creatorTheme={creatorTheme}
          onClose={() => setSelected(null)}
          onRetention={() => onOpenRetention(selected)}
        />
      )}
    </div>
  );
}

function Drawer({
  video,
  range,
  creatorTheme,
  onClose,
  onRetention,
}: {
  video: OwnedVideo;
  range: Range;
  creatorTheme?: CreatorPalette;
  onClose: () => void;
  onRetention: () => void;
}) {
  const d = useQuery({ queryKey: ["video", video.video_id, range], queryFn: () => api.videoDetail(video.video_id, range) });
  const m = d.data?.metrics;
  const primaryAccent = creatorTheme?.primary ?? "#67E8F9";

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/70 backdrop-blur-sm transition-opacity">
      <aside className="relative w-full max-w-md h-full overflow-y-auto border-l border-white/10 bg-[#08080c] p-6 shadow-2xl flex flex-col justify-between">
        <div>
          <div className="flex items-center justify-between pb-4 border-b border-white/[0.08]">
            <span className="text-xs font-mono font-bold tracking-widest text-[#ff1f3d] uppercase">Video Metrics</span>
            <button
              onClick={onClose}
              aria-label="Close"
              className="rounded-lg p-1.5 text-neutral-400 hover:text-white hover:bg-white/[0.05] transition-colors"
            >
              <X className="size-5" />
            </button>
          </div>

          {video.thumbnail_url && (
            <div className="mt-4 rounded-xl overflow-hidden border border-white/10 shadow-lg">
              <img src={video.thumbnail_url} alt="" className="w-full object-cover" />
            </div>
          )}

          <h3 className="mt-4 text-base font-bold text-white leading-snug">{video.title}</h3>
          <p className="mt-1 text-xs text-neutral-400 font-mono">
            {clock(video.duration_seconds)} · Published {shortDate(video.published_at)}
          </p>

          {d.isLoading && <Loading label="Loading video analytics..." />}
          {d.error && <ErrorBox error={d.error} />}

          {m && (
            <div className="mt-5 grid grid-cols-2 gap-3">
              <Stat label="Views" value={compact(m.views)} accentColor="#7DD3FC" />
              <Stat label="Watch Time" value={hours(m.watch_time_minutes)} accentColor="#C4B5FD" />
              <Stat
                label="Avg Duration"
                value={m.average_view_duration_seconds == null ? "—" : clock(m.average_view_duration_seconds)}
                accentColor="#93C5FD"
              />
              <Stat
                label="Avg View %"
                value={pct(m.average_view_percentage)}
                accentColor={primaryAccent}
              />
              <Stat label="Likes" value={compact(m.likes)} accentColor="#FDA4AF" />
              <Stat label="Comments" value={compact(m.comments)} accentColor="#FCD34D" />
              <Stat label="Subs Gained" value={compact(m.subscribers_gained)} accentColor="#86EFAC" />
              <Stat label="Subs Lost" value={compact(m.subscribers_lost)} accentColor="#FDA4AF" />
            </div>
          )}
        </div>

        <div className="pt-6">
          <a
            href={`/video/${video.video_id}`}
            className="retain-connect-btn block w-full rounded-xl py-3 text-center text-xs tracking-wider font-bold"
          >
            OPEN VIDEO INTELLIGENCE REPORT →
          </a>
        </div>

        <div className="pt-3">
          <button
            onClick={() => {
              onClose();
              onRetention();
            }}
            className="retain-connect-btn w-full rounded-xl py-3 text-xs tracking-wider font-bold"
          >
            VIEW AUDIENCE RETENTION CURVE →
          </button>
        </div>
      </aside>
    </div>
  );
}
