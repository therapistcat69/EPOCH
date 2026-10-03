import { API_BASE, ApiError, friendlyMessage, request } from "./api";
import type { Range } from "./creator-api";

export type Insight = { observation: string; interpretation: string; recommendation: string };
export type GroqState<T> = { available: boolean; report?: T; reason?: string; message?: string };

export type ChannelReport = {
  channel: { id: string; title: string };
  date_range: { start: string; end: string };
  cached: boolean;
  note: string;
  overview: {
    videos_in_library: number; videos_analyzed: number; total_views: number | null; total_watch_time_minutes: number | null;
    average_view_duration_seconds: number | null; average_view_percentage: number | null; subscribers_gained: number | null;
    subscribers_lost: number | null; net_subscribers: number | null; average_video_length_seconds: number | null;
    average_views_per_video: number | null; median_views_per_video: number | null; uploads_per_month: number | null;
  };
  content_patterns: {
    topics: { topic: string; videos: number; videos_with_analytics: number; median_views: number | null; average_view_percentage: number | null }[];
    formats: { format: string; count: number; share: number }[];
    title_patterns: { pattern: string; count: number; share: number }[];
    keywords: string[];
    common_video_lengths: { group: string; videos: number; median_views: number | null; average_view_percentage: number | null }[];
    transcript_insights: {
      videos_with_transcripts: number; average_words_per_minute: number | null; average_intro_hook_seconds: number | null;
      average_promise_gap_seconds: number | null; average_repetition_score: number | null; common_cta_types: string[]; recurring_themes: string[];
    };
  };
  performance_patterns: { kind: string; statement: string; n: number }[];
  groq: GroqState<{
    summary: string; strengths: string[]; weaknesses: string[]; content_patterns: string[];
    observed_performance_patterns: string[]; recommendations: Insight[]; experiments_to_try: string[];
  }>;
};

export type Segment = { segment_index: number; start_seconds: number; end_seconds: number; text: string; language?: string | null };
export type SegFeature = { segment_id: number; start: number; end: number; text: string; topic: string | null; summary: string | null; is_hook: boolean; is_question: boolean; is_cta: boolean; cta_types: string[]; repetition_score: number; semantic_novelty: number; information_density: number; topic_change: boolean };
export type DropOff = { from_ratio: number; to_ratio: number; from_seconds: number | null; to_seconds: number | null; drop: number; transcript: { start: number; end: number; text: string }[] };
export type RetentionPt = { time_ratio: number; audience_watch_ratio: number | null; relative_retention_performance: number | null };

export type VideoReport = {
  cached: boolean;
  video: { video_id: string; title: string; description: string; channel: string | null; published_at: string | null; duration_seconds: number | null; views: number | null; likes: number | null; comments: number | null; thumbnail_url: string | null };
  analytics: { metrics: { views: number | null; average_view_percentage: number | null; average_view_duration_seconds: number | null; watch_time_minutes: number | null } };
  retention: { available: boolean; points: RetentionPt[]; observed_drop_offs: DropOff[]; message: string | null };
  transcript: { available: boolean; provider?: string; language?: string | null; status?: string; timestamps_estimated?: boolean; message?: string; options?: string[] };
  features: {
    segments: SegFeature[]; repeated_ideas: { start: number; end: number; similar_to: { start: number; end: number }[]; similarity: number }[];
    ctas: { type: string; start: number; end: number; text: string }[];
  } | null;
  hook: { hook_latency_seconds: number | null; first_payoff_seconds: number | null; first_topic_reveal_seconds: number | null } | null;
  promise_gap: { promise_gap_seconds: number | null; note: string } | null;
  pacing: { average_words_per_minute: number | null; sentences_per_minute: number | null; mean_segment_seconds: number | null; topic_transitions: number; silence_rate: number | null } | null;
  repetition: { repeated_ideas: { start: number; end: number; similarity: number }[]; repetition_score: number | null } | null;
  cta: { ctas: { type: string; start: number; end: number; text: string }[] } | null;
  experiments: Insight[];
  predicted_retention: { available: boolean; message: string };
  groq: GroqState<{
    summary: string; strengths: string[]; weaknesses: string[]; hook_analysis: Insight; pacing_analysis: Insight; repetition_analysis: Insight; title_alignment: Insight;
    recommendations: { type: string; start: number | null; end: number | null; reason: string; evidence: string; confidence: number | null }[];
  }>;
};

export type TranscriptState = { available: boolean; segments: Segment[]; message?: string; options?: string[]; provider?: string; timestamps_estimated?: boolean };

export type Topic = {
  topic: string; sample_size: number; median_views: number | null; average_views: number | null; engagement_rate: number | null;
  recent_growth: number | null; momentum_score: number; momentum_label: "HIGH" | "MEDIUM" | "LOW"; momentum_version: string;
  common_formats: { format: string; share: number }[]; common_title_patterns: { pattern: string; count: number }[];
  example_videos: { video_id: string; title: string; views: number | null; channel: string | null }[]; top_channels: string[];
};
export type Trends = {
  genre: string; subgenre: string | null; sample_size: number; time_window: string; served_from_cache: boolean; search_calls_made: number;
  momentum_note: string; momentum_version: string; topics: Topic[];
  opportunities: { title: string; statement: string; evidence: string[] }[];
  genre_stats: { median_views: number | null; median_duration_seconds: number | null; unique_channels: number };
  ai_summary?: GroqState<{ summary: string; observed_opportunities: { title: string; evidence: string[]; suggested_experiment: string }[]; caveats: string[] }>;
};
export type Catalogue = { genres: { name: string; subgenres: string[] }[]; languages: { code: string; name: string }[]; regions: { code: string; name: string }[]; time_windows: string[] };
export type Benchmark = {
  status: "ok" | "insufficient_sample"; message: string | null; note: string; genre_sample_size: number;
  metrics: { metric: string; unit: string; channel: number | null; genre: number | null; difference: number | null; statement: string; suggested_experiment: string | null }[];
  formats: { name: string; channel_share: number; genre_share: number }[];
  title_patterns: { name: string; channel_share: number; genre_share: number }[];
  topics: { genre: { topic: string; share: number }[] };
};

const qs = (o: Record<string, string | undefined | boolean>) => {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(o)) if (v !== undefined && v !== "" && v !== false) p.set(k, String(v));
  const s = p.toString();
  return s ? `?${s}` : "";
};

export const intel = {
  channelReport: (r: Range, refresh = false) => request<ChannelReport>(`/api/channel/report${qs({ start_date: r.start, end_date: r.end, refresh })}`),
  videoReport: (id: string, refresh = false) => request<VideoReport>(`/api/video/${id}/report${qs({ refresh })}`),
  transcript: (id: string) => request<TranscriptState>(`/api/video/${id}/transcript`),
  uploadTranscript: (id: string, body: { format: "txt" | "srt" | "vtt"; content: string; language?: string }) =>
    request<TranscriptState>(`/api/video/${id}/transcript/upload`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
  transcribe: async (id: string, file: File, language?: string) => {
    const form = new FormData();
    form.append("file", file);
    if (language) form.append("language", language);
    return request<TranscriptState>(`/api/video/${id}/transcript/transcribe`, { method: "POST", body: form });
  },
  genres: () => request<Catalogue>("/api/genres"),
  trends: (p: { genre: string; subgenre?: string; language?: string; region?: string; time_window: string; refresh?: boolean; include_ai?: boolean }) =>
    request<Trends>(`/api/genres/${encodeURIComponent(p.genre)}/trends${qs({ subgenre: p.subgenre, language: p.language, region: p.region, time_window: p.time_window, refresh: p.refresh, include_ai: p.include_ai })}`),
  benchmark: (p: { genre: string; subgenre?: string; language?: string; region?: string; time_window: string }, r: Range) =>
    request<Benchmark>(`/api/channel/benchmark${qs({ ...p, start_date: r.start, end_date: r.end })}`),
  apiUsage: () => request<{ counters: Record<string, number>; note: string }>("/api/system/api-usage"),
};

export { ApiError, friendlyMessage, API_BASE };
