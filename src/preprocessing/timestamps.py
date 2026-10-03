"""Timestamp parsing and malformed-timestamp correction."""
import re

_TS = re.compile(r"^\s*(?:(\d+):)?(\d{1,2}):(\d{1,2})(?:[.,](\d{1,3}))?\s*$")
_NUM = re.compile(r"^\s*\d+(?:\.\d+)?\s*$")


def parse_timestamp(value) -> float:
    """'01:02:03,250' | '1:02' | '62.5' | 62.5 -> seconds. Raises ValueError on garbage."""
    if isinstance(value, (int, float)):
        if value < 0:
            raise ValueError("negative timestamp")
        return float(value)
    s = str(value).strip()
    if _NUM.match(s):
        return float(s)
    m = _TS.match(s)
    if not m:
        raise ValueError(f"unparseable timestamp: {value!r}")
    h, mnt, sec, ms = m.groups()
    return int(h or 0) * 3600 + int(mnt) * 60 + int(sec) + (int((ms or "0").ljust(3, "0")[:3]) / 1000)


def format_clock(seconds: float) -> str:
    s = int(round(max(seconds, 0)))
    return f"{s // 3600}:{(s % 3600) // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60:02d}:{s % 60:02d}"


def fix_cue_times(cues: list[dict], duration: float | None = None) -> tuple[list[dict], int]:
    """Repairs malformed timing: end < start (swap), negative values (clamp to 0), overlaps (trim the earlier cue's
    end to the next start), zero-length cues (minimum 0.5 s) and cues beyond the video duration (clamp).
    Returns (fixed cues sorted by start, number of corrections made)."""
    fixes = 0
    out = []
    for c in cues:
        s, e = float(c["start"]), float(c["end"])
        if s < 0 or e < 0:
            s, e, fixes = max(s, 0.0), max(e, 0.0), fixes + 1
        if e < s:
            s, e, fixes = e, s, fixes + 1
        if e - s < 0.5:
            e, fixes = s + 0.5, fixes + 1
        out.append({**c, "start": s, "end": e})
    out.sort(key=lambda c: (c["start"], c["end"]))
    for a, b in zip(out, out[1:]):
        if a["end"] > b["start"]:
            if b["start"] - a["start"] >= 0.5:
                a["end"] = b["start"]  # normal overlap: trim the earlier cue
            else:  # (near-)identical starts: keep the earlier cue intact and push the later one forward
                b["start"] = a["end"]
                b["end"] = max(b["end"], b["start"] + 0.5)
            fixes += 1
    if duration:
        for c in out:
            if c["end"] > duration:
                c["end"], fixes = duration, fixes + 1
        out = [c for c in out if c["start"] < duration]
    return out, fixes
