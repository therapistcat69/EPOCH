"""Model registry, training runs, real retention labels and prediction history (continuous-learning loop)."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.models.analysis import JsonType


class ModelVersion(Base):
    """statuses: candidate | production | rejected | archived. At most one row is `production`."""

    __tablename__ = "model_versions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    model_name: Mapped[str] = mapped_column(String(64))
    model_version: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    dataset_version: Mapped[str] = mapped_column(String(64))
    feature_schema_version: Mapped[str] = mapped_column(String(16))
    training_samples: Mapped[int] = mapped_column(Integer, default=0)
    real_samples: Mapped[int] = mapped_column(Integer, default=0)
    synthetic_samples: Mapped[int] = mapped_column(Integer, default=0)
    mae: Mapped[float | None] = mapped_column(Float, nullable=True)
    rmse: Mapped[float | None] = mapped_column(Float, nullable=True)
    r2: Mapped[float | None] = mapped_column(Float, nullable=True)
    pearson: Mapped[float | None] = mapped_column(Float, nullable=True)
    spearman: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(16), index=True)
    artifact_path: Mapped[str] = mapped_column(Text)
    trained_on: Mapped[str] = mapped_column(String(32), default="synthetic")
    metadata_json: Mapped[dict | None] = mapped_column(JsonType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TrainingRun(Base):
    __tablename__ = "training_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    model_name: Mapped[str] = mapped_column(String(64))
    dataset_version: Mapped[str] = mapped_column(String(64))
    feature_schema_version: Mapped[str] = mapped_column(String(16))
    reason: Mapped[str] = mapped_column(String(32), default="manual")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16), index=True)  # running | completed | failed
    training_samples: Mapped[int] = mapped_column(Integer, default=0)
    validation_samples: Mapped[int] = mapped_column(Integer, default=0)
    test_samples: Mapped[int] = mapped_column(Integer, default=0)
    metrics_json: Mapped[dict | None] = mapped_column(JsonType, nullable=True)
    artifact_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    candidate_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    decision: Mapped[str | None] = mapped_column(Text, nullable=True)


class PredictionHistory(Base):
    """Prediction stored BEFORE publication; the actual curve and error are filled in once YouTube Analytics has it."""

    __tablename__ = "prediction_history"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    video_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    transcript_hash: Mapped[str] = mapped_column(String(64))
    prediction_model_version: Mapped[str] = mapped_column(String(32))
    feature_schema_version: Mapped[str] = mapped_column(String(16))
    dataset_version: Mapped[str] = mapped_column(String(64))
    predicted_curve: Mapped[list] = mapped_column(JsonType)
    actual_curve: Mapped[list | None] = mapped_column(JsonType, nullable=True)
    error_metrics: Mapped[dict | None] = mapped_column(JsonType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RealTrainingLabel(Base):
    """A real, creator-authorized labelled example (transcript + actual YouTube retention). data_source is always real_youtube."""

    __tablename__ = "real_training_labels"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    video_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("videos.id", ondelete="CASCADE"), unique=True, index=True)
    data_source: Mapped[str] = mapped_column(String(16), default="real_youtube")
    dataset_version: Mapped[str] = mapped_column(String(64), default="real_v1")
    transcript_hash: Mapped[str] = mapped_column(String(64))
    actual_curve: Mapped[list] = mapped_column(JsonType)
    used_in_model_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
