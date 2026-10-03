"""Configurable fixed-length segmentation (10 / 15 / 20 / 30 s ...). Original timestamps are preserved.

Each caption cue is split WORD-WISE across the windows it overlaps, interpolating word times inside the cue, so a
long cue that straddles a boundary contributes to both windows. Empty windows are kept (silent / no captions).
"""
import math
from dataclasses import dataclass

from src.preprocessing.canonical import Transcript
from src.preprocessing.cleaning import clean_text


@dataclass
class Segment:
    video_id: str
    segment_id: int
    start_time: float
    end_time: float
    raw_text: str
    text: str            # cleaned
    absolute_time: float  # = start_time (seconds from video start)
    relative_position: float  # = start_time / duration
    cue_ids: list
    is_empty: bool


def segment_transcript(tr: Transcript, segment_seconds: float = 15.0, duration: float | None = None) -> list[Segment]:
    if segment_seconds <= 0:
        raise ValueError("segment_seconds must be positive")
    duration = duration or tr.duration or (max((c["end"] for c in tr.cues), default=0.0))
    if duration <= 0:
        return []
    n = max(1, math.ceil(duration / segment_seconds))
    raw_words: list[list[str]] = [[] for _ in range(n)]
    clean_words: list[list[str]] = [[] for _ in range(n)]
    cue_ids: list[set] = [set() for _ in range(n)]
    for c in tr.cues:
        raw = c.get("raw_text", c["text"]).split()
        clean = c["text"].split()
        if not raw and not clean:
            continue
        span = max(c["end"] - c["start"], 1e-6)
        for words, store in ((raw, raw_words), (clean, clean_words)):
            for i, w in enumerate(words):
                tw = c["start"] + (i + 0.5) / len(words) * span
                idx = min(int(tw // segment_seconds), n - 1)
                store[idx].append(w)
                cue_ids[idx].add(c["segment_id"])
    segs = []
    for i in range(n):
        start = i * segment_seconds
        end = min((i + 1) * segment_seconds, duration)
        text = clean_text(" ".join(clean_words[i]))
        segs.append(Segment(
            video_id=tr.video_id, segment_id=i, start_time=round(start, 3), end_time=round(end, 3),
            raw_text=" ".join(raw_words[i]), text=text, absolute_time=round(start, 3),
            relative_position=round(start / duration, 6), cue_ids=sorted(cue_ids[i]), is_empty=not text.strip(),
        ))
    return segs
