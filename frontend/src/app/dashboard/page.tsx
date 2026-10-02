"use client";
/* eslint-disable @next/next/no-img-element */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, LogOut, RefreshCw } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Audience, Traffic } from "@/components/dashboard/Breakdowns";
import Overview from "@/components/dashboard/Overview";
import RetentionPanel from "@/components/dashboard/Retention";
import { Empty, ErrorBox, Loading } from "@/components/dashboard/ui";
import Videos from "@/components/dashboard/Videos";
import { ApiError } from "@/lib/api";
import { api, type OwnedVideo, type Range } from "@/lib/creator-api";
import { iso, rangeForDays, shortDate } from "@/lib/format";

const TABS = ["Overview", "Videos", "Retention", "Audience", "Traffic"] as const;
type Tab = (typeof TABS)[number];
const PRESETS: [string, number][] = [["Last 7 days", 7], ["Last 28 days", 28], ["Last 90 days", 90], ["Last 365 days", 365]];

export default function Dashboard() {
  const router = useRouter();
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>("Overview");
  const [preset, setPreset] = useState("28");
  const [custom, setCustom] = useState<Range>(rangeForDays(28));
  const range: Range = preset === "custom" ? custom : rangeForDays(Number(preset));
  const [retentionVideo, setRetentionVideo] = useState<OwnedVideo | null>(null);

  const me = useQuery({ queryKey: ["me"], queryFn: api.me });
  useEffect(() => {
    if (me.data && !me.data.authenticated) router.replace("/login");
  }, [me.data, router]);

  const authed = !!me.data?.authenticated;
  const channel = useQuery({ queryKey: ["channel"], queryFn: api.channel, enabled: authed });

  // Sync: start a background job, poll its status, refresh data when done
  const [syncId, setSyncId] = useState<string | null>(null);
  const start = useMutation({ mutationFn: api.startSync, onSuccess: (r) => setSyncId(r.sync_id) });
  const status = useQuery({
    queryKey: ["sync", syncId],
    queryFn: () => api.syncStatus(syncId!),
    enabled: !!syncId,
    refetchInterval: (q) => (q.state.data && ["completed", "failed"].includes(q.state.data.status) ? false : 1000),
  });
  const syncDone = status.data?.status === "completed";
  useEffect(() => {
    if (syncDone) qc.invalidateQueries();
  }, [syncDone, qc]);
  const syncing = start.isPending || (!!syncId && !!status.data && !["completed", "failed"].includes(status.data.status));

  const logout = useMutation({
    mutationFn: api.logout,
    onSuccess: () => {
      qc.clear();
      router.replace("/login");
    },
  });

  const videosForPicker = useQuery({
    queryKey: ["picker", range],
    queryFn: () => api.videos(range, { page: 1, limit: 100, sort: "newest", search: "" }),
    enabled: authed && tab === "Retention",
  });

  if (me.isLoading) return <Loading label="Checking your session…" />;
  if (me.error) return <div className="mx-auto max-w-xl p-8"><ErrorBox error={me.error} /></div>;
  if (!authed) return <Loading label="Redirecting to sign in…" />;

  const needsAuth = (e: unknown) => e instanceof ApiError && ["NOT_AUTHENTICATED", "REAUTH_REQUIRED", "TOKEN_INVALID"].includes(e.code);
  if (needsAuth(channel.error)) router.replace("/login?error=REAUTH_REQUIRED");

  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="text-sm font-semibold tracking-[0.3em] text-red-500">RETAINAI</span>
          {me.data?.channel?.thumbnail_url && <img src={me.data.channel.thumbnail_url} alt="" className="size-8 rounded-full" />}
          <div>
            <div className="font-semibold leading-tight">{me.data?.channel?.title}</div>
            <div className="text-xs text-neutral-500">
              {syncing ? status.data?.step ?? "Starting sync..." : channel.data?.last_synced_at ? `Last synced ${shortDate(channel.data.last_synced_at)}` : "Not synced yet"}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => start.mutate()} disabled={syncing} className="flex items-center gap-2 rounded-lg bg-red-600 px-3 py-2 text-sm font-medium text-white disabled:opacity-60">
            {syncing ? <Loader2 className="size-4 animate-spin" /> : <RefreshCw className="size-4" />} Sync YouTube Data
          </button>
          <button onClick={() => logout.mutate()} className="flex items-center gap-2 rounded-lg border border-neutral-400/40 px-3 py-2 text-sm">
            <LogOut className="size-4" /> Logout
          </button>
        </div>
      </header>

      {(start.error || status.data?.status === "failed") && (
        <div className="mt-3"><ErrorBox error={start.error ?? new Error(status.data?.error_message ?? "Sync failed.")} /></div>
      )}
      {syncDone && <p className="mt-3 text-sm text-green-500">Sync complete.</p>}

      <nav className="mt-6 flex flex-wrap items-center justify-between gap-3 border-b border-neutral-400/30">
        <div className="flex gap-1">
          {TABS.map((t) => (
            <button key={t} onClick={() => setTab(t)} className={`px-3 py-2 text-sm ${tab === t ? "border-b-2 border-red-500 font-semibold" : "text-neutral-500"}`}>
              {t}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2 pb-2 text-sm">
          <select value={preset} onChange={(e) => setPreset(e.target.value)} className="rounded-lg border border-neutral-400/40 bg-transparent px-2 py-1">
            {PRESETS.map(([l, d]) => <option key={d} value={d} className="text-black">{l}</option>)}
            <option value="custom" className="text-black">Custom</option>
          </select>
          {preset === "custom" && (
            <>
              <input type="date" value={custom.start} max={custom.end} onChange={(e) => setCustom({ ...custom, start: e.target.value })} className="rounded-lg border border-neutral-400/40 bg-transparent px-2 py-1" />
              <input type="date" value={custom.end} max={iso(new Date())} onChange={(e) => setCustom({ ...custom, end: e.target.value })} className="rounded-lg border border-neutral-400/40 bg-transparent px-2 py-1" />
            </>
          )}
        </div>
      </nav>

      <main className="mt-4">
        {tab === "Overview" && <Overview range={range} subscribers={channel.data?.subscriber_count ?? null} />}
        {tab === "Videos" && <Videos range={range} onOpenRetention={(v) => { setRetentionVideo(v); setTab("Retention"); }} />}
        {tab === "Audience" && <Audience range={range} />}
        {tab === "Traffic" && <Traffic range={range} />}
        {tab === "Retention" && (
          <div className="space-y-4">
            <label className="block text-sm">
              <span className="mb-1 block text-neutral-500">Select a video</span>
              <select
                value={retentionVideo?.video_id ?? ""}
                onChange={(e) => setRetentionVideo(videosForPicker.data?.items.find((i) => i.video.video_id === e.target.value)?.video ?? null)}
                className="w-full rounded-lg border border-neutral-400/40 bg-transparent px-3 py-2"
              >
                <option value="" className="text-black">Choose a video…</option>
                {retentionVideo && !videosForPicker.data?.items.some((i) => i.video.video_id === retentionVideo.video_id) && (
                  <option value={retentionVideo.video_id} className="text-black">{retentionVideo.title}</option>
                )}
                {videosForPicker.data?.items.map(({ video }) => <option key={video.video_id} value={video.video_id} className="text-black">{video.title}</option>)}
              </select>
            </label>
            {videosForPicker.isLoading && <Loading />}
            {videosForPicker.error && <ErrorBox error={videosForPicker.error} />}
            {videosForPicker.data?.total === 0 && <Empty>No videos yet. Click “Sync YouTube Data”.</Empty>}
            {retentionVideo ? <RetentionPanel key={retentionVideo.video_id} video={retentionVideo} range={range} /> : <Empty>Pick a video to load its audience retention curve.</Empty>}
          </div>
        )}
      </main>
    </div>
  );
}
