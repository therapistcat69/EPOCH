from pydantic import BaseModel

from app.schemas.features import FeaturePayload


ML_FEATURE_SCHEMA_VERSION = "1.0"


class RetentionFeatures(BaseModel):
    """Observed YouTube retention curve, as parallel arrays (raw, unsmoothed)."""

    time_ratio: list[float] = []
    audience_watch_ratio: list[float | None] = []
    relative_retention_performance: list[float | None] = []


class MLVideoFeatures(BaseModel):
    """Versioned contract handed to the ML team for a creator's video.

    Anything not computed in this phase is None / empty ({}), never faked.
    Ratios: average_view_percentage is 0-1 here (YouTube's percent / 100).
    """

    feature_schema_version: str = ML_FEATURE_SCHEMA_VERSION
    video_id: str
    title: str
    category: str | None = None
    duration_seconds: int | None = None
    views: int | None = None
    likes: int | None = None
    comments: int | None = None
    average_view_duration: float | None = None  # seconds
    average_view_percentage: float | None = None  # 0-1 ratio
    retention: RetentionFeatures = RetentionFeatures()
    analytics_features: dict = {}
    content_features: dict = {}
    audio_features: dict = {}
    language_features: dict = {}
    retention_features: dict = {}


class PredictRequest(BaseModel):
    video_id: str
    features: FeaturePayload


class PredictResponse(BaseModel):
    """Shape the future model service must return."""

    model_name: str
    model_version: str
    score: float
    prediction: str
    confidence: float | None = None
