from typing import Literal

from pydantic import BaseModel

FEATURE_SCHEMA_VERSION = "1.0"

# Research features that a future preprocessing pipeline must supply.
# Never fabricated here: they stay None until that pipeline exists.
PENDING_FEATURES = (
    "title_word_count",
    "document_entropy",
    "freshness",
    "easiness",
    "fraction_stopword_presence",
    "speaker_speed",
    "silent_period_rate",
)


class FeaturePayload(BaseModel):
    schema_version: str = FEATURE_SCHEMA_VERSION
    video_id: str
    title: str
    duration_seconds: int
    category_id: str | None = None
    view_count: int | None = None
    like_count: int | None = None
    comment_count: int | None = None

    # To be filled by the future ML / preprocessing pipeline.
    title_word_count: int | None = None
    document_entropy: float | None = None
    freshness: float | None = None
    easiness: float | None = None
    fraction_stopword_presence: float | None = None
    speaker_speed: float | None = None
    silent_period_rate: float | None = None

    language: str | None = None
    transcript_available: bool = False


FeatureStatus = Literal["available", "pending_pipeline"]
