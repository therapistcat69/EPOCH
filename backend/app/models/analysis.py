import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base

# JSONB on Postgres, plain JSON elsewhere (SQLite in tests / local fallback).
JsonType = JSON().with_variant(JSONB(), "postgresql")


class VideoAnalysis(Base):
    __tablename__ = "video_analysis"
    __table_args__ = (Index("ix_video_analysis_video_created", "video_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    video_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("videos.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(32), default="completed")
    raw_api_response: Mapped[dict | None] = mapped_column(JsonType, nullable=True)
    normalized_data: Mapped[dict | None] = mapped_column(JsonType, nullable=True)
    feature_payload: Mapped[dict | None] = mapped_column(JsonType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class FuturePrediction(Base):
    """Destination for the ML team's output. Intentionally never written in this phase."""

    __tablename__ = "future_predictions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    video_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("videos.id", ondelete="CASCADE"))
    model_name: Mapped[str] = mapped_column(String(64))
    model_version: Mapped[str] = mapped_column(String(32))
    prediction_status: Mapped[str] = mapped_column(String(32), default="pending")
    predicted_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    prediction_json: Mapped[dict | None] = mapped_column(JsonType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
