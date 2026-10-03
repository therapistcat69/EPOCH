"""Transcripts, content features, stored retention points, reports and trend tables."""
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.models.analysis import JsonType


def _created() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now())


def _updated() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class VideoTranscript(Base):
    __tablename__ = "video_transcripts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    video_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    provider: Mapped[str] = mapped_column(String(32))  # uploaded | groq_whisper | youtube_captions
    full_text: Mapped[str] = mapped_column(Text)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="ready")
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


class TranscriptSegment(Base):
    __tablename__ = "transcript_segments"
    __table_args__ = (Index("ix_segments_transcript_start", "transcript_id", "start_seconds"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    transcript_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("video_transcripts.id", ondelete="CASCADE"), index=True
    )
    segment_index: Mapped[int] = mapped_column(Integer)
    start_seconds: Mapped[float] = mapped_column(Float)
    end_seconds: Mapped[float] = mapped_column(Float)
    text: Mapped[str] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = _created()


class ContentFeature(Base):
    """Deterministic CONTENT features (not retention predictions). One row per video."""

    __tablename__ = "content_features"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    video_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("videos.id", ondelete="CASCADE"), unique=True)
    feature_schema_version: Mapped[str] = mapped_column(String(16), default="1.0")
    title_word_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description_word_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hook_latency_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    promise_gap_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    average_words_per_minute: Mapped[float | None] = mapped_column(Float, nullable=True)
    repetition_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    semantic_novelty: Mapped[float | None] = mapped_column(Float, nullable=True)
    information_density: Mapped[float | None] = mapped_column(Float, nullable=True)
    topic_clusters: Mapped[list | None] = mapped_column(JsonType, nullable=True)
    format: Mapped[str | None] = mapped_column(String(48), nullable=True)
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    genre: Mapped[str | None] = mapped_column(String(64), nullable=True)
    subgenre: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cta_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cta_timestamps: Mapped[list | None] = mapped_column(JsonType, nullable=True)
    features_json: Mapped[dict | None] = mapped_column(JsonType, nullable=True)  # full analysis incl. per-segment
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


class VideoRetentionPoint(Base):
    """Raw YouTube retention values, stored unmodified."""

    __tablename__ = "video_retention_points"
    __table_args__ = (UniqueConstraint("video_id", "time_ratio"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    video_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    time_ratio: Mapped[float] = mapped_column(Float)
    absolute_time_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    audience_watch_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    relative_retention_performance: Mapped[float | None] = mapped_column(Float, nullable=True)
    started_watching: Mapped[float | None] = mapped_column(Float, nullable=True)
    stopped_watching: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = _created()


class ChannelReport(Base):
    __tablename__ = "channel_reports"
    __table_args__ = (UniqueConstraint("user_id", "channel_id", "date_start", "date_end"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    channel_id: Mapped[str] = mapped_column(String(64), index=True)
    date_start: Mapped[str] = mapped_column(String(10))
    date_end: Mapped[str] = mapped_column(String(10))
    structured_report_json: Mapped[dict] = mapped_column(JsonType)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


class VideoReport(Base):
    __tablename__ = "video_reports"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    video_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("videos.id", ondelete="CASCADE"), unique=True)
    structured_report_json: Mapped[dict] = mapped_column(JsonType)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


class TrendSearchCache(Base):
    __tablename__ = "trend_search_cache"
    __table_args__ = (Index("ix_trend_cache_lookup", "genre", "subgenre", "language", "region", "time_window"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    genre: Mapped[str] = mapped_column(String(64))
    subgenre: Mapped[str | None] = mapped_column(String(64), nullable=True)
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    region: Mapped[str | None] = mapped_column(String(8), nullable=True)
    time_window: Mapped[str] = mapped_column(String(8))
    query: Mapped[str] = mapped_column(String(255))
    video_ids: Mapped[list] = mapped_column(JsonType)
    created_at: Mapped[datetime] = _created()
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class TrendTopic(Base):
    __tablename__ = "trend_topics"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    genre: Mapped[str] = mapped_column(String(64), index=True)
    subgenre: Mapped[str | None] = mapped_column(String(64), nullable=True)
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    region: Mapped[str | None] = mapped_column(String(8), nullable=True)
    time_window: Mapped[str | None] = mapped_column(String(8), nullable=True)
    topic_name: Mapped[str] = mapped_column(String(255))
    sample_size: Mapped[int] = mapped_column(Integer)
    median_views: Mapped[float | None] = mapped_column(Float, nullable=True)
    average_views: Mapped[float | None] = mapped_column(Float, nullable=True)
    engagement_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    momentum_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    momentum_version: Mapped[str] = mapped_column(String(16))
    common_formats: Mapped[list | None] = mapped_column(JsonType, nullable=True)
    common_title_patterns: Mapped[list | None] = mapped_column(JsonType, nullable=True)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


class GenreBenchmark(Base):
    __tablename__ = "genre_benchmarks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    genre: Mapped[str] = mapped_column(String(64), index=True)
    subgenre: Mapped[str | None] = mapped_column(String(64), nullable=True)
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    region: Mapped[str | None] = mapped_column(String(8), nullable=True)
    time_window: Mapped[str | None] = mapped_column(String(8), nullable=True)
    sample_size: Mapped[int] = mapped_column(Integer)
    stats: Mapped[dict] = mapped_column(JsonType)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = _updated()


class MLPrediction(Base):
    """Destination for the ML team's output (never written in this phase). Mirrors future_predictions
    with the richer contract (curve + risk segments)."""

    __tablename__ = "ml_predictions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    video_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("videos.id", ondelete="CASCADE"), index=True)
    model_name: Mapped[str] = mapped_column(String(64))
    model_version: Mapped[str] = mapped_column(String(32))
    prediction_json: Mapped[dict | None] = mapped_column(JsonType, nullable=True)
    created_at: Mapped[datetime] = _created()
