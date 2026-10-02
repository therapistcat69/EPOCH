import { request } from "./api";
import { clearRetainAISession, getRetainAISession } from "./auth";

export type Metrics = {
  views: number | null;
  engaged_views: number | null;
  watch_time_minutes: number | null;
  average_view_duration_seconds: number | null;
  average_view_percentage: number | null;
  likes: number | null;
  comments: number | null;
  shares: number | null;
  subscribers_gained: number | null;
  subscribers_lost: number | null;
  net_subscribers: number | null;
};
export type Envelope = { start_date: string; end_date: string; cached: boolean; fetched_at: string | null };
export type Me = {
  authenticated: boolean;
  user: { name: string | null; email: string | null; image: string | null } | null;
  channel: { id: string; title: string; thumbnail_url: string | null } | null;
};
export type OwnedChannel = {
  channel_id: string;
  title: string;
  subscriber_count: number | null;
  total_views: number | null;
  video_count: number | null;
  last_synced_at: string | null;
};
export type OwnedVideo = {
  video_id: string;
  title: string;
  thumbnail_url: string | null;
  published_at: string | null;
  duration_seconds: number | null;
  privacy_status: string | null;
};
export type VideoRow = { video: OwnedVideo; metrics: Metrics | null };
export type Insights = {
  videos_analyzed: number;
  average_view_percentage: number | null;
  median_view_percentage: number | null;
  average_view_duration_seconds: number | null;
  median_view_duration_seconds: number | null;
  average_views_per_video: number | null;
};
export type VideosResponse = Envelope & { items: VideoRow[]; total: number; page: number; limit: number; insights: Insights };
export type Point = { date: string; views: number | null; watch_time_minutes: number | null; subscribers_gained: number | null; subscribers_lost: number | null; net_subscribers: number | null };
export type RetentionPoint = {
  time_ratio: number;
  audience_watch_ratio: number | null;
  relative_retention_performance: number | null;
};
export type DropOff = { from_ratio: number; to_ratio: number; from_seconds: number | null; to_seconds: number | null; drop: number };
export type Retention = Envelope & {
  video_id: string;
  duration_seconds: number | null;
  points: RetentionPoint[];
  observed_drop_offs: DropOff[];
};
export type BreakdownRow = { key: string; views: number | null; watch_time_minutes: number | null; average_view_duration_seconds: number | null; average_view_percentage: number | null };
export type SyncStatus = { sync_id: string; status: "started" | "running" | "completed" | "failed"; step: string | null; error_message: string | null };

export type Range = { start: string; end: string };
const q = (r: Range, extra: Record<string, string | number | undefined> = {}) => {
  const p = new URLSearchParams({ start_date: r.start, end_date: r.end });
  for (const [k, v] of Object.entries(extra)) if (v !== undefined && v !== "") p.set(k, String(v));
  return `?${p}`;
};
const post = { method: "POST" } as const;

export const api = {
  me: async (): Promise<Me> => {
    try {
      const backendMe = await request<Me>("/api/auth/me");
      if (backendMe?.authenticated) {
        return backendMe;
      }
    } catch {
      // Backend unauthenticated or offline
    }
    const localUser = getRetainAISession();
    if (localUser) {
      return {
        authenticated: true,
        user: { name: localUser.name, email: localUser.email, image: null },
        channel: null,
      };
    }
    return { authenticated: false, user: null, channel: null };
  },
  logout: async () => {
    clearRetainAISession();
    try {
      await request<{ ok: boolean }>("/api/auth/logout", post);
    } catch {
      // ignore
    }
    return { ok: true };
  },
  channel: () => request<OwnedChannel>("/api/channel/me"),
  overview: (r: Range, refresh = false) => request<Envelope & { metrics: Metrics }>(`/api/analytics/overview${q(r, { refresh: refresh ? "true" : undefined })}`),
  timeseries: (r: Range) => request<Envelope & { points: Point[] }>(`/api/analytics/timeseries${q(r)}`),
  videos: (r: Range, o: { page: number; limit: number; sort: string; search: string }) =>
    request<VideosResponse>(`/api/analytics/videos${q(r, o)}`),
  retention: (id: string) => request<Retention>(`/api/analytics/video/${id}/retention`),
  videoDetail: (id: string, r: Range) => request<Envelope & { video: OwnedVideo; metrics: Metrics }>(`/api/analytics/video/${id}${q(r)}`),
  breakdown: (kind: "traffic-sources" | "geography" | "devices", r: Range) =>
    request<Envelope & { rows: BreakdownRow[] }>(`/api/analytics/${kind}${q(r)}`),
  startSync: () => request<{ sync_id: string; status: string }>("/api/sync", post),
  syncStatus: (id: string) => request<SyncStatus>(`/api/sync/${id}`),
};
export const loginUrl = `${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"}/api/auth/youtube/login`;
