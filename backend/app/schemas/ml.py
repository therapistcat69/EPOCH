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


class MLRetentionInput(BaseModel):
    time_ratio: list[float] = []
    audience_watch_ratio: list[float | None] = []
    relative_retention_performance: list[float | None] = []


class MLInput(BaseModel):
    """Full future model input (feature-store contract). Unavailable groups are empty, never faked."""

    feature_schema_version: str = ML_FEATURE_SCHEMA_VERSION
    video_id: str
    duration_seconds: int | None = None
    metadata: dict = {}
    analytics: dict = {}
    retention: MLRetentionInput = MLRetentionInput()
    transcript_features: dict = {}
    audio_features: dict = {}
    visual_features: dict = {}
    title_features: dict = {}
    genre_features: dict = {}


class RiskSegment(BaseModel):
    start_seconds: float
    end_seconds: float
    risk: float
    reason_features: list[str] = []


class MLOutput(BaseModel):
    """Shape the future model service must return from POST /api/ml/predict."""

    video_id: str
    model_name: str
    model_version: str
    retention_curve: list[float] = []
    risk_segments: list[RiskSegment] = []
    confidence: float | None = None


class MLStatus(BaseModel):
    available: bool = False
    model_name: str | None = None
    model_version: str | None = None
    message: str = "ML model not connected."


class MLPredictRequest(BaseModel):
    """POST /api/ml/predict body. `transcript` uses the canonical schema {segments:[{segment_id,start,end,text}]};
    `video` holds metadata (title, description, duration_seconds, category). `features` may carry features already
    computed by the application's transcript pipeline (consumed, not recomputed, when compatible)."""

    video_id: str
    video: dict = {}
    transcript: dict = {}
    features: dict = {}


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
