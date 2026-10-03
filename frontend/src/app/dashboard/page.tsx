"use client";
/* eslint-disable @next/next/no-img-element */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowUpRight, CheckCircle2, Film, Loader2, LogOut, PlaySquare, RefreshCw, Sparkles, Users, Video } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { Audience, Traffic } from "@/components/dashboard/Breakdowns";
import ConnectYouTubeScreen from "@/components/dashboard/ConnectYouTubeScreen";
import LogoutButton from "@/components/dashboard/LogoutButton";
import Overview from "@/components/dashboard/Overview";
import ChannelIntelligence from "@/components/intel/ChannelIntelligence";
import RetentionPanel from "@/components/dashboard/Retention";
import { Empty, ErrorBox, Loading } from "@/components/dashboard/ui";
import RetainLoadingState from "@/components/RetainLoadingState";
import Videos from "@/components/dashboard/Videos";
import { ApiError } from "@/lib/api";
import { api, loginUrl, type OwnedVideo, type Range } from "@/lib/creator-api";
import { generateCreatorTheme, getCreatorCssVariables } from "@/lib/creatorTheme";
import { compact, iso, rangeForDays, shortDate } from "@/lib/format";

const TABS = ["Overview", "Channel Report", "Videos", "Retention", "Audience", "Traffic"] as const;
type Tab = (typeof TABS)[number];
const PRESETS: [string, number][] = [
  ["Last 7 days", 7],
  ["Last 28 days", 28],
  ["Last 90 days", 90],
  ["Last 365 days", 365],
];

export default function Dashboard() {
  return (
    <Suspense fallback={<Loading label="Loading your dashboard" sub="Fetching your latest data..." />}>
      <DashboardContent />
    </Suspense>
  );
}

function DashboardContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const errorParam = searchParams?.get("error");
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
  const hasChannel = !!me.data?.channel;
  const channel = useQuery({ queryKey: ["channel"], queryFn: api.channel, enabled: authed && hasChannel });

  // Sync: start background job, poll status, refresh queries when finished
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
    enabled: authed && hasChannel && tab === "Retention",
  });

  // Handle errors
  const getErrorMessage = () => {
    if (!errorParam) return null;
    switch (errorParam) {
      case "OAUTH_DENIED":
        return "Google authorization was cancelled. Please authorize YouTube access to continue.";
      case "OAUTH_CALLBACK_FAILED":
        return "Authentication callback failed. Please retry connecting your channel.";
      case "OAUTH_NOT_CONFIGURED":
        return "OAuth is currently being configured on the server.";
      case "REAUTH_REQUIRED":
        return "Session expired or channel access revoked. Please reconnect.";
      default:
        return "An authentication error occurred. Please try again.";
    }
  };

  if (me.isLoading) return <Loading label="Loading your dashboard" sub="Fetching your latest data..." />;
  if (me.error) return <div className="mx-auto max-w-xl p-8"><ErrorBox error={me.error} /></div>;
  if (!authed) return <Loading label="Loading your dashboard" sub="Redirecting to sign in…" />;

  if (hasChannel) {
    const needsAuth = (e: unknown) =>
      e instanceof ApiError && ["NOT_AUTHENTICATED", "REAUTH_REQUIRED", "TOKEN_INVALID"].includes(e.code);
    if (needsAuth(channel.error)) router.replace("/login?error=REAUTH_REQUIRED");
  }

  if (hasChannel && channel.isLoading) {
    return <Loading label="Fetching your YouTube data" sub="Loading your latest analytics..." />;
  }

  // ============================================================
  // UNCONNECTED STATE: Render the Cinematic ConnectYouTubeScreen
  // ============================================================
  if (!hasChannel) {
    return (
      <ConnectYouTubeScreen
        userName={me.data?.user?.name}
        userEmail={me.data?.user?.email}
        loginUrl={loginUrl}
        onLogout={() => logout.mutate()}
        isLoggingOut={logout.isPending}
        errorMessage={getErrorMessage()}
      />
    );
  }

  // ============================================================
  // CONNECTED CREATOR STATE: Apply Personalized Theme Palette
  // ============================================================
  const channelIdentifier = channel.data?.channel_id || me.data?.channel?.id || me.data?.user?.email;
  const creatorTheme = generateCreatorTheme(channelIdentifier);
  const themeCss = getCreatorCssVariables(creatorTheme);

  return (
    <div
      style={themeCss}
      className="min-h-screen w-full bg-[#030303] text-white selection:bg-[#ff1f3d] selection:text-white"
    >
      <div className="mx-auto w-full max-w-6xl px-4 sm:px-6 py-6 space-y-6">
        {/* ============================================================
            TOP COCKPIT HEADER
            ============================================================ */}
        <header className="flex flex-wrap items-center justify-between gap-4 border-b border-white/[0.08] pb-5">
          <div className="flex items-center gap-3.5">
            <span className="text-lg font-black tracking-[0.3em] text-[#ff1f3d]">RETAINAI</span>
            <div className="h-5 w-[1px] bg-white/10" />
            <span
              className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-mono font-medium"
              style={{
                backgroundColor: creatorTheme.badgeBg,
                color: creatorTheme.primary,
                border: `1px solid ${creatorTheme.border}`,
              }}
            >
              <span className="size-1.5 rounded-full animate-pulse" style={{ backgroundColor: creatorTheme.primary }} />
              {creatorTheme.name} Cockpit
            </span>
          </div>

          <div className="flex items-center gap-2.5">
            <a
              href="/trends"
              className="nav-trace-btn px-3.5 py-2 text-xs font-semibold"
            >
              <span className="relative z-10">Trends</span>
            </a>
            <a
              href="/benchmark"
              className="nav-trace-btn px-3.5 py-2 text-xs font-semibold"
            >
              <span className="relative z-10">Benchmark</span>
            </a>
            <a
              href="/models"
              className="nav-trace-btn px-3.5 py-2 text-xs font-semibold"
            >
              <span className="relative z-10">Models</span>
            </a>
            <a
              href="/analyze"
              className="nav-trace-btn px-3.5 py-2 text-xs font-semibold"
            >
              <span className="relative z-10">Analyze</span>
            </a>
            <button
              onClick={() => start.mutate()}
              disabled={syncing}
              className="nav-trace-btn px-3.5 py-2 text-xs font-semibold disabled:opacity-50 disabled:pointer-events-none"
            >
              <span className="relative z-10 flex items-center gap-2">
                <RefreshCw className={`size-3.5 text-[#ff1f3d] ${syncing ? "animate-spin" : ""}`} />
                <span>{syncing ? "Syncing…" : "Sync Data"}</span>
              </span>
            </button>
            <LogoutButton onLogout={() => logout.mutate()} isLoggingOut={logout.isPending} />
          </div>
        </header>

        {/* Sync Feedback alerts */}
        {(start.error || status.data?.status === "failed") && (
          <ErrorBox error={start.error ?? new Error(status.data?.error_message ?? "Sync failed.")} />
        )}
        {syncDone && (
          <div className="flex items-center gap-2 rounded-xl border border-green-500/20 bg-green-950/20 p-3 text-xs text-green-300">
            <CheckCircle2 className="size-4 text-green-400" />
            <span>Channel library synchronized with latest YouTube Analytics.</span>
          </div>
        )}

        {syncing ? (
          <div className="relative overflow-hidden rounded-2xl border border-white/[0.08] bg-[#09090d]/90 backdrop-blur-2xl p-8 sm:p-14 shadow-2xl">
            <RetainLoadingState
              title="Syncing your YouTube data"
              subtitle={status.data?.step ?? "Fetching your latest analytics..."}
              minHeight="min-h-[380px]"
            />
          </div>
        ) : (
          <>
            {/* ============================================================
                CHANNEL HERO / OVERVIEW BAR (Personalized Creator Identity)
                ============================================================ */}
            <section className="relative overflow-hidden rounded-2xl border border-white/[0.08] bg-[#09090d]/90 backdrop-blur-2xl p-5 sm:p-6 shadow-2xl">
          {/* Subtle Accent Glow behind Avatar */}
          <div
            className="pointer-events-none absolute -left-10 -top-10 size-48 rounded-full blur-[60px] opacity-40"
            style={{ backgroundColor: creatorTheme.primary }}
          />

          <div className="relative z-10 flex flex-col sm:flex-row sm:items-center justify-between gap-5">
            <div className="flex items-center gap-4">
              {/* Creator Channel Avatar */}
              <div
                className="relative size-14 rounded-2xl overflow-hidden border p-[2px] shrink-0"
                style={{
                  borderColor: creatorTheme.primary,
                  boxShadow: `0 0 20px ${creatorTheme.glow}`,
                }}
              >
                {me.data?.channel?.thumbnail_url ? (
                  <img
                    src={me.data.channel.thumbnail_url}
                    alt={me.data.channel.title}
                    className="size-full rounded-[14px] object-cover"
                  />
                ) : (
                  <div className="size-full bg-neutral-900 rounded-[14px] flex items-center justify-center text-white font-bold">
                    {me.data?.channel?.title?.charAt(0) || "C"}
                  </div>
                )}
              </div>

              <div>
                <div className="flex items-center gap-2">
                  <h1 className="text-lg sm:text-xl font-extrabold text-white tracking-tight">
                    {me.data?.channel?.title}
                  </h1>
                  <span className="flex items-center gap-1 rounded-full bg-white/[0.04] border border-white/10 px-2 py-0.5 text-[10px] font-mono text-neutral-300">
                    <span className="size-1.5 rounded-full bg-emerald-400" />
                    YouTube Connected
                  </span>
                </div>
                <p className="text-xs text-neutral-400 mt-1">
                  Understand your retention before your next upload. ·{" "}
                  <span className="font-mono text-neutral-500">
                    {channel.data?.last_synced_at
                      ? `Synced ${shortDate(channel.data.last_synced_at)}`
                      : "Awaiting sync"}
                  </span>
                </p>
              </div>
            </div>

            {/* Quick Metrics & Retention Jump Action */}
            <div className="flex items-center gap-4 border-t sm:border-t-0 border-white/[0.06] pt-3 sm:pt-0">
              <div className="text-left sm:text-right">
                <div className="text-[11px] font-semibold uppercase tracking-wider text-neutral-400 font-mono">
                  Subscribers
                </div>
                <div className="text-lg font-bold text-white tracking-tight">
                  {channel.data?.subscriber_count ? compact(channel.data.subscriber_count) : "—"}
                </div>
              </div>

              <div className="h-8 w-[1px] bg-white/[0.08]" />

              <button
                onClick={() => setTab("Retention")}
                className="retain-connect-btn rounded-xl px-4 py-2 text-xs font-bold tracking-wider"
              >
                ANALYZE RETENTION →
              </button>
            </div>
          </div>
        </section>

        {/* ============================================================
            NAVIGATION TABS & RANGE SELECTOR
            ============================================================ */}
        <nav className="flex flex-wrap items-center justify-between gap-4 border-b border-white/[0.08] pb-1">
          <div className="flex items-center gap-2 sm:gap-4 overflow-x-auto">
            {TABS.map((t) => {
              const isActive = tab === t;
              return (
                <button
                  key={t}
                  onClick={() => setTab(t)}
                  className={`relative py-2.5 px-3 text-xs sm:text-sm font-semibold tracking-wider transition-all duration-200 ${
                    isActive ? "text-white" : "text-neutral-500 hover:text-neutral-300"
                  }`}
                >
                  {t}
                  {isActive && (
                    <span
                      className="absolute bottom-0 left-0 right-0 h-[2px] rounded-full"
                      style={{ backgroundColor: creatorTheme.primary }}
                    />
                  )}
                </button>
              );
            })}
          </div>

          {/* Date Presets Dropdown */}
          <div className="flex items-center gap-2 pb-1 text-xs">
            <select
              value={preset}
              onChange={(e) => setPreset(e.target.value)}
              className="rounded-xl border border-white/10 bg-[#0c0d14] px-3 py-1.5 text-xs text-white focus:border-white/25 focus:outline-none"
            >
              {PRESETS.map(([l, d]) => (
                <option key={d} value={d} className="bg-neutral-900 text-white">
                  {l}
                </option>
              ))}
              <option value="custom" className="bg-neutral-900 text-white">
                Custom Range
              </option>
            </select>
            {preset === "custom" && (
              <div className="flex items-center gap-1.5">
                <input
                  type="date"
                  value={custom.start}
                  max={custom.end}
                  onChange={(e) => setCustom({ ...custom, start: e.target.value })}
                  className="rounded-xl border border-white/10 bg-[#0c0d14] px-2.5 py-1 text-xs text-white"
                />
                <span className="text-neutral-500 font-mono">→</span>
                <input
                  type="date"
                  value={custom.end}
                  max={iso(new Date())}
                  onChange={(e) => setCustom({ ...custom, end: e.target.value })}
                  className="rounded-xl border border-white/10 bg-[#0c0d14] px-2.5 py-1 text-xs text-white"
                />
              </div>
            )}
          </div>
        </nav>

        {/* ============================================================
            TAB WORKSPACE
            ============================================================ */}
        <main className="pt-2">
          {tab === "Overview" && (
            <Overview
              range={range}
              subscribers={channel.data?.subscriber_count ?? null}
              creatorTheme={creatorTheme}
            />
          )}

          {tab === "Channel Report" && <ChannelIntelligence range={range} />}

          {tab === "Videos" && (
            <Videos
              range={range}
              creatorTheme={creatorTheme}
              onOpenRetention={(v) => {
                setRetentionVideo(v);
                setTab("Retention");
              }}
            />
          )}

          {tab === "Audience" && (
            <Audience range={range} creatorTheme={creatorTheme} />
          )}

          {tab === "Traffic" && (
            <Traffic range={range} creatorTheme={creatorTheme} />
          )}

          {tab === "Retention" && (
            <div className="space-y-6">
              {/* Video Selector Dropdown */}
              <div className="rounded-2xl border border-white/[0.08] bg-[#09090d]/85 p-5 shadow-2xl backdrop-blur-xl">
                <label className="block text-xs uppercase font-mono font-semibold text-neutral-400 tracking-wider mb-2">
                  Select a video from your library to examine audience retention
                </label>
                <select
                  value={retentionVideo?.video_id ?? ""}
                  onChange={(e) =>
                    setRetentionVideo(
                      videosForPicker.data?.items.find((i) => i.video.video_id === e.target.value)?.video ?? null
                    )
                  }
                  className="w-full rounded-xl border border-white/10 bg-[#0c0d14] px-3.5 py-2.5 text-xs text-white focus:border-white/25 focus:outline-none"
                >
                  <option value="" className="bg-neutral-900 text-neutral-400">
                    Choose a video from your channel…
                  </option>
                  {retentionVideo &&
                    !videosForPicker.data?.items.some((i) => i.video.video_id === retentionVideo.video_id) && (
                      <option value={retentionVideo.video_id} className="bg-neutral-900 text-white">
                        {retentionVideo.title}
                      </option>
                    )}
                  {videosForPicker.data?.items.map(({ video }) => (
                    <option key={video.video_id} value={video.video_id} className="bg-neutral-900 text-white">
                      {video.title} ({shortDate(video.published_at)})
                    </option>
                  ))}
                </select>
              </div>

              {videosForPicker.isLoading && <Loading label="Loading your video catalog…" />}
              {videosForPicker.error && <ErrorBox error={videosForPicker.error} />}
              {videosForPicker.data?.total === 0 && (
                <Empty>No videos available yet. Click “Sync Data” above to load your channel.</Empty>
              )}

              {retentionVideo ? (
                <RetentionPanel
                  key={retentionVideo.video_id}
                  video={retentionVideo}
                  range={range}
                  creatorTheme={creatorTheme}
                />
              ) : (
                <div className="rounded-2xl border border-dashed border-white/10 p-12 text-center bg-white/[0.01]">
                  <PlaySquare className="mx-auto size-8 text-neutral-500 mb-2" />
                  <p className="text-xs text-neutral-400 font-mono uppercase tracking-wider">
                    Pick a video from the dropdown above to load its audience retention curve.
                  </p>
                </div>
              )}
            </div>
          )}
        </main>
          </>
        )}
      </div>
    </div>
  );
}
