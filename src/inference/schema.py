"""PredictionResult: the stable output contract of the ML engine (what the application consumes).

PREDICTED data is kept strictly separate from OBSERVED data. `trained_on` / `data_mode` say what the model was
trained on; a model trained on synthetic data must never be presented as validated on real YouTube retention.
"""
from typing import Literal

from pydantic import BaseModel, Field


class PredictionPoint(BaseModel):
    start_seconds: float
    end_seconds: float
    time_ratio: float  # start_seconds / duration
    predicted_retention: float = Field(ge=0, le=100)


class NormalizedPoint(BaseModel):
    """Prediction resampled onto YouTube Analytics' normalized grid (elapsedVideoTimeRatio 0.00 .. 1.00)."""

    time_ratio: float
    predicted_retention: float


class ContributingFactor(BaseModel):
    feature: str
    group: str
    contribution: float  # model-attribution value (SHAP / ablation effect) toward higher predicted risk
    direction: Literal["high", "low"]  # the segment's value relative to the rest of the video
    label: str  # e.g. "high redundancy with earlier content"


class RiskSegment(BaseModel):
    start_seconds: float
    end_seconds: float
    risk_score: float = Field(ge=0, le=1)  # monotone rescaling of predicted local decline; NOT a calibrated probability
    predicted_drop: float  # predicted retention decline across the region (percentage points)
    contributing_features: list[str]
    factors: list[ContributingFactor] = []
    explanation: str = ""
    explanation_type: Literal["MODEL-BASED EXPLANATION"] = "MODEL-BASED EXPLANATION"  # not a causal reason


class Uncertainty(BaseModel):
    available: bool = False
    method: str | None = None
    std: list[float] = []  # per prediction point
    lower: list[float] = []
    upper: list[float] = []
    note: str = "uncertainty estimate unavailable"


class EditSuggestion(BaseModel):
    """Future schema for actionable edits. predicted_effect stays None until a validated counterfactual model exists."""

    edit_type: Literal["cut", "tighten", "move", "rewrite", "add", "test", "other"]
    start: float
    end: float
    reason: str
    evidence: list[str] = []
    predicted_effect: None = None


class PredictionResult(BaseModel):
    video_id: str
    model_name: str
    model_version: str
    feature_schema_version: str
    dataset_version: str
    trained_on: Literal["synthetic", "real", "synthetic+real"]
    data_mode_warning: str | None = None
    segment_seconds: float
    duration_seconds: float
    embedding_model: str
    points: list[PredictionPoint]
    normalized_curve: list[NormalizedPoint] = []
    risk_segments: list[RiskSegment] = []
    uncertainty: Uncertainty = Uncertainty()
    warnings: list[str] = []


class PredictRequest(BaseModel):
    """POST /api/ml/predict body. Provide `transcript` (canonical schema) and `video` metadata; `features` are optional
    precomputed values from the application's transcript pipeline (consumed, not recomputed, when compatible)."""

    video_id: str
    video: dict = {}
    transcript: dict = {}
    features: dict = {}
