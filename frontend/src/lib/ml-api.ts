import { request } from "./api";
import type { GroqState } from "./intel-api";

export type MlStatus = {
  model_available: boolean;
  state: "not_started" | "loading" | "ready" | "unavailable";
  model_name: string | null;
  model_version: string | null;
  feature_schema_version: string | null;
  dataset_version: string | null;
  trained_on: "synthetic" | "real" | "synthetic+real" | null;
  training_samples: number | null;
  synthetic_samples: number | null;
  real_samples: number | null;
  last_trained: string | null;
  embedding_model: string | null;
  segment_seconds: number | null;
  real_validation_available: boolean;
  message: string;
};

export type Factor = { feature: string; group: string; contribution: number; direction: "high" | "low"; label: string };
export type RiskRegion = {
  start_seconds: number;
  end_seconds: number;
  risk_score: number;
  predicted_drop: number;
  contributing_features: string[];
  factors: Factor[];
  explanation: string;
  explanation_type: string;
};
export type Prediction = {
  video_id: string;
  model_name: string;
  model_version: string;
  trained_on: "synthetic" | "real" | "synthetic+real";
  data_mode_warning: string | null;
  duration_seconds: number;
  segment_seconds: number;
  embedding_model: string;
  points: { start_seconds: number; end_seconds: number; time_ratio: number; predicted_retention: number }[];
  normalized_curve: { time_ratio: number; predicted_retention: number }[];
  risk_segments: RiskRegion[];
  uncertainty: { available: boolean; method: string | null; std: number[]; lower: number[]; upper: number[]; note: string };
  warnings: string[];
};
export type MlExplanation = GroqState<{ summary: string; risk_explanations: { start_seconds: number; end_seconds: number; what_is_happening: string; possible_experiment: string }[] }>;

export type ModelRow = {
  id: string; model_name: string; model_version: string; dataset_version: string; feature_schema_version: string;
  training_samples: number; real_samples: number; synthetic_samples: number;
  mae: number | null; rmse: number | null; r2: number | null; pearson: number | null; spearman: number | null;
  status: "candidate" | "production" | "rejected" | "archived"; trained_on: string; created_at: string | null;
};
export type TrainingRun = { id: string; reason: string; status: string; candidate_version: string | null; started_at: string | null; completed_at: string | null; decision: string | null };
export type MlMetrics = {
  current_model: ModelRow | null; prediction_count: number; real_labeled_videos: number;
  average_recent_error_mae: number | null; recent_error_samples: number; drift_warning: boolean | null; drift_note?: string;
};
export type TextPrediction = { prediction: Prediction; transcript: { segments: { segment_id: number; start: number; end: number; text: string }[]; timestamps_estimated: boolean; language: string | null } };

export type DemoVideo = { video_id: string; title: string; archetype: string; duration_seconds: number };
export type DemoDetail = {
  video_id: string;
  title: string;
  duration_seconds: number;
  label: string;
  disclaimer: string;
  transcript: { segments: { segment_id: number; start: number; end: number; text: string }[] };
  synthetic_target: { time_ratio: number; retention: number }[];
  prediction: Prediction;
  groq?: MlExplanation;
};
export type VideoPrediction =
  | { available: false; reason: string; message: string }
  | { available: true; prediction: Prediction; actual: { available: boolean; note: string; points: { time_ratio: number; value: number }[] }; groq?: MlExplanation };

const qs = (o: Record<string, string | boolean | undefined>) => {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(o)) if (v) p.set(k, String(v));
  const s = p.toString();
  return s ? `?${s}` : "";
};

const admin = (token: string) => ({ headers: { "Content-Type": "application/json", ...(token ? { "x-admin-token": token } : {}) } });

export const ml = {
  models: () => request<{ models: ModelRow[]; training_runs: TrainingRun[]; retrain_after_real_labels: number }>("/api/ml/models"),
  metrics: () => request<MlMetrics>("/api/ml/metrics"),
  retrain: (token: string) => request<{ candidate_version: string; status: string; note: string }>("/api/ml/retrain", { method: "POST", body: JSON.stringify({ reason: "manual", force: false }), ...admin(token) }),
  promote: (version: string, token: string) => request<ModelRow>(`/api/ml/models/${version}/promote`, { method: "POST", ...admin(token) }),
  predictText: (body: { title: string; format: "txt" | "srt" | "vtt"; content: string; duration_seconds?: number }) =>
    request<TextPrediction>("/api/ml/predict-text", { method: "POST", body: JSON.stringify(body), headers: { "Content-Type": "application/json" } }),
  status: () => request<MlStatus>("/api/ml/status"),
  demoVideos: () => request<{ label: string; videos: DemoVideo[] }>("/api/ml/demo/videos"),
  demo: (id: string, explain = false) => request<DemoDetail>(`/api/ml/demo/${id}${qs({ explain })}`),
  videoPrediction: (id: string, includeAi = false) => request<VideoPrediction>(`/api/video/${id}/prediction${qs({ include_ai: includeAi })}`),
};
