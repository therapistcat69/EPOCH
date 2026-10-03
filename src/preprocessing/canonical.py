"""One canonical internal transcript schema, independent of the provider.

    {"video_id": "...", "segments": [{"segment_id": 1, "start": 0.0, "end": 15.0, "text": "..."}]}

Accepts the synthetic raw format (start_time/end_time), the RetainAI backend transcript format
(start_seconds/end_seconds/segment_index) from uploaded TXT/SRT/VTT, authorized captions or Groq Whisper, and
plain dicts. The ML pipeline never depends on which provider produced the transcript.
"""
from dataclasses import dataclass, field

from src.preprocessing.cleaning import clean_text, remove_duplicate_cues
from src.preprocessing.timestamps import fix_cue_times, parse_timestamp


@dataclass
class Transcript:
    video_id: str
    cues: list[dict]  # {segment_id, start, end, text, raw_text}
    duration: float | None = None
    corrections: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return dict(video_id=self.video_id, segments=[dict(segment_id=c["segment_id"], start=c["start"], end=c["end"], text=c["text"]) for c in self.cues])


def _pick(d: dict, *names, default=None):
    for n in names:
        if n in d and d[n] is not None:
            return d[n]
    return default


def canonicalize(video_id: str, segments: list[dict], duration: float | None = None) -> Transcript:
    cues = []
    bad = 0
    for i, s in enumerate(segments):
        try:
            start = parse_timestamp(_pick(s, "start", "start_time", "start_seconds"))
            end = parse_timestamp(_pick(s, "end", "end_time", "end_seconds", default=start))
        except (ValueError, TypeError):
            bad += 1
            continue
        raw = str(_pick(s, "text", default=""))
        cues.append(dict(segment_id=int(_pick(s, "segment_id", "segment_index", default=i)), start=start, end=end, text=raw, raw_text=raw))
    cues, fixes = fix_cue_times(cues, duration)
    cues, dups = remove_duplicate_cues(cues)
    for c in cues:
        c["text"] = clean_text(c["raw_text"] if "raw_text" in c else c["text"])
    for i, c in enumerate(cues):
        c["segment_id"] = i
    if duration is None and cues:
        duration = max(c["end"] for c in cues)
    return Transcript(video_id, cues, duration, dict(unparseable_dropped=bad, time_fixes=fixes, duplicates_removed=dups))
