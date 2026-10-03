"""THE ML PLUG-IN POINT: the application talks to `PredictionService` and does not care whether the model behind it is
Random Forest, XGBoost, LSTM or a Transformer.

`RetentionMLService` delegates to the ML engine (repo-root `src/`, see docs/ml-integration.md) through `ml_bridge`.
When no trained artifact is available, `get_prediction_service()` returns `NotConnectedPredictionService` (501).
"""
import asyncio
from typing import Protocol

from app.errors import AppError
from app.schemas.ml import MLInput
from app.services import ml_bridge


class PredictionService(Protocol):
    async def predict(self, request) -> dict: ...


class NotConnectedPredictionService:
    async def predict(self, request) -> dict:
        raise AppError("ML_NOT_IMPLEMENTED", "The ML prediction pipeline is not connected yet.", 501)


class RetentionMLService:
    """Runs the RetainAI ML engine in a worker thread (model inference is CPU-bound)."""

    async def predict(self, request) -> dict:
        predictor = ml_bridge.get_predictor()
        video, transcript = request.video or {}, request.transcript or {}
        segments = transcript.get("segments") or []
        if not segments:
            raise AppError("TRANSCRIPT_REQUIRED", "A transcript with timestamped segments is required for retention prediction.", 422)
        duration = float(video.get("duration_seconds") or video.get("duration") or transcript.get("duration") or max(float(s.get("end", s.get("end_seconds", s.get("end_time", 0))) or 0) for s in segments))
        if duration <= 0:
            raise AppError("INVALID_DURATION", "The video duration could not be determined.", 422)
        try:
            result = await asyncio.to_thread(
                predictor.predict, request.video_id, str(video.get("title") or ""), str(video.get("description") or ""), duration, segments
            )
        except ValueError as exc:
            raise AppError("PREDICTION_FAILED", f"Could not predict: {exc}", 422)
        return result.model_dump()


def get_prediction_service() -> PredictionService:
    st = ml_bridge.status()["state"]
    return RetentionMLService() if st in ("ready", "loading") else NotConnectedPredictionService()


def build_ml_input(report: dict) -> MLInput:
    """Maps a stored video report (real data only) onto the feature-store contract (MLInput) for external model teams."""
    pts = report.get("retention", {}).get("points", [])
    feats = report.get("features") or {}
    v = report["video"]
    return MLInput(
        video_id=v["video_id"], duration_seconds=v.get("duration_seconds"),
        metadata={k: v.get(k) for k in ("title", "channel", "published_at", "views", "likes", "comments")},
        analytics=report.get("analytics", {}).get("metrics", {}),
        retention={
            "time_ratio": [p["time_ratio"] for p in pts],
            "audience_watch_ratio": [p["audience_watch_ratio"] for p in pts],
            "relative_retention_performance": [p["relative_retention_performance"] for p in pts],
        },
        transcript_features={k: feats[k] for k in (
            "hook_latency_seconds", "promise_gap_seconds", "average_words_per_minute", "repetition_score",
            "semantic_novelty", "information_density", "topic_transitions") if k in feats},
        title_features={"title_word_count": len((v.get("title") or "").split())},
    )
