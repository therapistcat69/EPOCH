import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class SegmentIn(BaseModel):
    segment_index: int
    start_seconds: float
    end_seconds: float
    text: str
    language: str | None = None


class TranscriptData(BaseModel):
    """Provider-independent internal transcript."""

    language: str | None = None
    provider: str  # uploaded | groq_whisper | youtube_captions
    duration_seconds: float | None = None
    segments: list[SegmentIn]
    timestamps_estimated: bool = False

    @property
    def full_text(self) -> str:
        return " ".join(s.text for s in self.segments)


class TranscriptUpload(BaseModel):
    format: Literal["txt", "srt", "vtt"]
    content: str
    language: str | None = None


class TranscriptSegmentOut(SegmentIn):
    pass


class TranscriptOut(BaseModel):
    available: bool
    video_id: str
    transcript_id: uuid.UUID | None = None
    provider: str | None = None
    language: str | None = None
    duration_seconds: float | None = None
    status: str | None = None
    timestamps_estimated: bool = False
    segments: list[TranscriptSegmentOut] = []
    created_at: datetime | None = None
    message: str | None = None  # e.g. "Transcript unavailable for this video."
    options: list[str] = []  # e.g. ["upload_transcript", "upload_audio"]
