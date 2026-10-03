"""Transcript acquisition via official/authorized routes only (no scraping).

Providers, in explicit order of preference:
  1. YouTubeCaptionProvider  - authorized caption download (needs extra OAuth scope; opt-in)
  2. UploadedTranscriptProvider - user-supplied TXT / SRT / VTT
  3. GroqWhisperProvider     - user-supplied audio, transcribed by Groq Whisper
If none is possible the caller reports "Transcript unavailable" - the rest of the report still works.
"""
import re
from typing import Protocol

from app.config import get_settings
from app.errors import AppError
from app.schemas.transcript import SegmentIn, TranscriptData
from app.services.groq_service import GroqService
from app.services.nlp import word_count
from app.services.youtube_client import YouTubeClient

_TS = r"(?:(\d+):)?(\d{1,2}):(\d{2})(?:[.,](\d{1,3}))?"
_TIMING_RE = re.compile(rf"{_TS}\s*-->\s*{_TS}")
_LEADING_TS_RE = re.compile(rf"^\s*[\[(]?{_TS}[\])]?\s*[-–:]?\s*(.*)$")
_TAG_RE = re.compile(r"<[^>]+>|\{\\[^}]*\}")


def _secs(h: str | None, m: str, s: str, ms: str | None) -> float:
    return int(h or 0) * 3600 + int(m) * 60 + int(s) + (int((ms or "0").ljust(3, "0")[:3]) / 1000)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", _TAG_RE.sub("", text)).strip()


def parse_cues(content: str) -> list[SegmentIn]:
    """Parses SRT and WebVTT (both use 'start --> end' cue timings)."""
    text = content.replace("\r\n", "\n").replace("\r", "\n").lstrip("﻿")
    segments: list[SegmentIn] = []
    for block in re.split(r"\n\s*\n", text):
        lines = [ln for ln in block.split("\n") if ln.strip()]
        timing_idx = next((i for i, ln in enumerate(lines) if _TIMING_RE.search(ln)), None)
        if timing_idx is None:
            continue  # WEBVTT header, NOTE/STYLE blocks, stray text
        g = _TIMING_RE.search(lines[timing_idx]).groups()
        start, end = _secs(*g[0:4]), _secs(*g[4:8])
        cue_text = _clean(" ".join(lines[timing_idx + 1 :]))
        if cue_text:
            segments.append(SegmentIn(segment_index=len(segments), start_seconds=start, end_seconds=max(end, start), text=cue_text))
    return segments


def parse_plain_text(content: str, duration_seconds: float | None) -> tuple[list[SegmentIn], bool]:
    """TXT: honours leading 'mm:ss text' timestamps when every line has one; otherwise
    splits into sentences and ESTIMATES timing proportionally to word count (flagged)."""
    lines = [ln.strip() for ln in content.replace("\r", "").split("\n") if ln.strip()]
    stamped = [(_LEADING_TS_RE.match(ln)) for ln in lines]
    if lines and all(stamped):
        points = [(_secs(*m.groups()[0:4]), _clean(m.group(5))) for m in stamped]
        segs = []
        for i, (start, txt) in enumerate(points):
            end = points[i + 1][0] if i + 1 < len(points) else (duration_seconds or start + max(2.0, word_count(txt) / 2.5))
            if txt:
                segs.append(SegmentIn(segment_index=len(segs), start_seconds=start, end_seconds=max(end, start), text=txt))
        return segs, False

    sentences = [s.strip() for s in re.split(r"(?<=[.!?।])\s+|\n+", " ".join(lines)) if s.strip()]
    total_words = sum(max(word_count(s), 1) for s in sentences) or 1
    total = duration_seconds or total_words / 2.5  # assume ~150 wpm when duration is unknown
    segs, t = [], 0.0
    for s in sentences:
        dur = total * max(word_count(s), 1) / total_words
        segs.append(SegmentIn(segment_index=len(segs), start_seconds=round(t, 2), end_seconds=round(t + dur, 2), text=s))
        t += dur
    return segs, True


def parse_upload(fmt: str, content: str, language: str | None, duration_seconds: float | None) -> TranscriptData:
    if not content or not content.strip():
        raise AppError("TRANSCRIPT_EMPTY", "The transcript is empty.", 422)
    estimated = False
    if fmt in ("srt", "vtt"):
        segments = parse_cues(content)
    else:
        segments, estimated = parse_plain_text(content, duration_seconds)
    if not segments:
        raise AppError("TRANSCRIPT_PARSE_FAILED", f"Couldn't read any {fmt.upper()} cues from that transcript.", 422)
    for s in segments:
        s.language = language
    return TranscriptData(
        language=language, provider="uploaded", segments=segments, timestamps_estimated=estimated,
        duration_seconds=max(s.end_seconds for s in segments),
    )


# ---------------------------------------------------------------- providers
class TranscriptProvider(Protocol):
    name: str


class UploadedTranscriptProvider:
    name = "uploaded"

    def parse(self, fmt: str, content: str, language: str | None, duration_seconds: float | None) -> TranscriptData:
        return parse_upload(fmt, content, language, duration_seconds)


class GroqWhisperProvider:
    name = "groq_whisper"

    def __init__(self, groq: GroqService):
        self.groq = groq

    async def transcribe(self, audio: bytes, filename: str, language: str | None) -> TranscriptData:
        max_bytes = get_settings().max_audio_mb * 1024 * 1024
        if len(audio) > max_bytes:
            raise AppError("AUDIO_TOO_LARGE", f"Audio must be under {get_settings().max_audio_mb} MB. Compress or trim it first.", 413)
        result = await self.groq.transcribe(audio, filename, language)
        segs = [
            SegmentIn(segment_index=i, start_seconds=s.start, end_seconds=s.end, text=s.text, language=result.language)
            for i, s in enumerate(result.segments)
        ]
        return TranscriptData(
            language=result.language or language, provider=self.name, duration_seconds=result.duration or segs[-1].end_seconds,
            segments=segs,
        )


class YouTubeCaptionProvider:
    """Authorized caption download. captions.download requires the youtube.force-ssl scope (edit
    permission), which this app does NOT request by default. Disabled unless ENABLE_CAPTION_DOWNLOAD=true
    and the account was authorized with that scope; otherwise it reports 'unavailable' - never scrapes."""

    name = "youtube_captions"

    def __init__(self, client: YouTubeClient):
        self.client = client

    async def fetch(self, video_id: str) -> TranscriptData | None:
        if not get_settings().enable_caption_download:
            return None
        try:
            tracks = (await self.client.caption_tracks(video_id)).get("items", [])
            if not tracks:
                return None
            srt = await self.client.download_caption(tracks[0]["id"])
        except AppError:
            return None  # no permission / not available: caller falls back to upload
        segments = parse_cues(srt)
        if not segments:
            return None
        lang = tracks[0].get("snippet", {}).get("language")
        return TranscriptData(
            language=lang, provider=self.name, segments=segments, duration_seconds=max(s.end_seconds for s in segments)
        )


UNAVAILABLE_MESSAGE = "Transcript unavailable for this video."
UNAVAILABLE_OPTIONS = ["upload_transcript", "upload_audio"]
