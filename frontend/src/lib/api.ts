const BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(public code: string, message: string) {
    super(message);
  }
}

// Friendly copy per backend error code. Raw backend text is never shown.
const MESSAGES: Record<string, string> = {
  INVALID_URL: "That doesn't look like a valid YouTube video link.",
  VIDEO_NOT_FOUND: "We couldn't find that video. It may be private or deleted.",
  CHANNEL_NOT_FOUND: "We couldn't find that channel.",
  ANALYSIS_NOT_FOUND: "That analysis no longer exists.",
  QUOTA_EXCEEDED: "The YouTube API quota is used up for today. Try again later.",
  RATE_LIMITED: "Too many requests. Please wait a moment and retry.",
  API_KEY_MISSING: "The server isn't configured with a YouTube API key yet.",
  API_KEY_INVALID: "The server's YouTube API key is invalid.",
  API_NOT_ENABLED: "The YouTube Data API isn't enabled for the server's Google project yet.",
  FORBIDDEN: "YouTube refused the request. Check the server's API key settings.",
  UPSTREAM_ERROR: "YouTube is having trouble right now. Please try again.",
  NETWORK: "Can't reach the backend. Is it running?",
  NOT_AUTHENTICATED: "Please sign in with YouTube to continue.",
  REAUTH_REQUIRED: "Your Google connection expired. Please sign in again.",
  TOKEN_INVALID: "Your Google session is no longer valid. Please sign in again.",
  ANALYTICS_PERMISSION: "YouTube Analytics refused access. Sign in again and approve the analytics permission.",
  REPORTING_PERMISSION: "YouTube Reporting refused access. Sign in again and approve the analytics permission.",
  ANALYTICS_UNAVAILABLE: "YouTube has no analytics for this video or date range yet.",
  INVALID_DATE_RANGE: "That date range isn't valid. Pick a start date on or before the end date.",
  OAUTH_NOT_CONFIGURED: "Google sign-in isn't configured on the server yet.",
  OAUTH_DENIED: "Sign-in was cancelled. Nothing was connected.",
  OAUTH_CALLBACK_FAILED: "Google sign-in failed. Please try again.",
  INVALID_STATE: "The sign-in attempt couldn't be verified. Please try again.",
  SCOPE_MISSING: "Both YouTube permissions are required. Please sign in again and leave both boxes ticked.",
  NO_CHANNEL: "We connected your Google account, but no YouTube channel was found for this account.",
  API_KEY_RESTRICTED: "The server's API key is restricted and can't call the YouTube Data API.",
};

export function friendlyMessage(code: string): string {
  return MESSAGES[code] ?? "Something went wrong. Please try again.";
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    // credentials: the HttpOnly session cookie is sent to the backend; no token ever touches JavaScript
    res = await fetch(`${BASE}${path}`, { credentials: "include", ...init });
  } catch {
    throw new ApiError("NETWORK", MESSAGES.NETWORK);
  }
  if (!res.ok) {
    let code = "INTERNAL_ERROR";
    try {
      code = (await res.json()).error?.code ?? code;
    } catch {}
    throw new ApiError(code, friendlyMessage(code));
  }
  return res.json();
}

export const API_BASE = BASE;

export type Video = {
  video_id: string;
  url: string;
  title: string;
  channel: { id: string | null; title: string | null };
  published_at: string | null;
  duration_formatted: string;
  category_name: string | null;
  statistics: { views: number | null; likes: number | null; comments: number | null };
  thumbnail_url: string | null;
};

export type Channel = {
  channel_id: string;
  title: string;
  subscriber_count: number | null;
  total_views: number | null;
  video_count: number | null;
};

export type Report = {
  analysis_id: string;
  cached: boolean;
  video: Video;
  channel: Channel | null;
  features: Record<string, unknown>;
  feature_readiness: Record<string, "available" | "pending_pipeline">;
  source: string;
};

export type Summary = { analysis_id: string; title: string; channel_title: string | null };

export const analyze = (youtube_url: string) =>
  request<Report>("/api/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ youtube_url }),
  });
export const getReport = (id: string) => request<Report>(`/api/analyses/${id}`);
export const getRecent = () => request<Summary[]>("/api/analyses?limit=6");
