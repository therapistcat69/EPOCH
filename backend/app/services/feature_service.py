"""Computes and stores deterministic content features for a video (the ML-facing feature store)."""
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ContentFeature, Video
from app.repositories import intel_repository as repo
from app.schemas.transcript import SegmentIn
from app.services import nlp
from app.services.content_patterns import detect_format
from app.services.transcript_analysis_service import (
    FEATURE_SCHEMA_VERSION,
    TranscriptAnalysis,
    analyze_transcript,
)


def top_terms_for(segments: list[SegmentIn], k: int = 8) -> list[str]:
    return nlp.top_terms([nlp.tokenize(s.text) for s in segments], k=k)


async def analyze_and_store(
    session: AsyncSession, video: Video, segments: list[SegmentIn], language: str | None,
    genre: str | None = None, subgenre: str | None = None,
) -> tuple[TranscriptAnalysis, ContentFeature]:
    analysis = analyze_transcript(segments, video.title, video.description, video.duration_seconds)
    payload = analysis.model_dump(mode="json")
    payload["top_terms"] = top_terms_for(segments)
    row = await repo.upsert_content_features(
        session, video.id,
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        title_word_count=nlp.word_count(video.title),
        description_word_count=nlp.word_count(video.description or ""),
        duration_seconds=video.duration_seconds,
        hook_latency_seconds=analysis.hook_latency_seconds,
        promise_gap_seconds=analysis.promise_gap_seconds,
        average_words_per_minute=analysis.average_words_per_minute,
        repetition_score=analysis.repetition_score,
        semantic_novelty=analysis.semantic_novelty,
        information_density=analysis.information_density,
        topic_clusters=[],
        format=detect_format(video.title, video.description),
        language=language,
        genre=genre, subgenre=subgenre,
        cta_count=len(analysis.ctas),
        cta_timestamps=[{"type": c.type, "start": c.start, "end": c.end} for c in analysis.ctas],
        features_json=payload,
    )
    return analysis, row
