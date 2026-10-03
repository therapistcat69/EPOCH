"""Transcript cleaning. The RAW text is always kept; cleaning produces a separate CLEANED text.

Deliberately NOT done: stopword removal. Words like not / never / but / however / although change meaning and are
preserved.
"""
import re

_ARTIFACT = re.compile(r"[\[(]\s*(music|applause|laughter|laughs|cheering|noise|silence|inaudible|background noise)[^\])]*[\])]|♪+|♫+", re.I)
_SPACES = re.compile(r"\s+")
_SPACE_BEFORE_PUNCT = re.compile(r"\s+([,.!?;:])")
_REPEAT_PUNCT = re.compile(r"([!?.,])\1{2,}")
_SMART = str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'", "–": "-", "—": "-", "…": "..."})
_WORD = re.compile(r"[\w']+", re.U)


def clean_text(text: str) -> str:
    t = (text or "").translate(_SMART)
    t = _ARTIFACT.sub(" ", t)
    t = _REPEAT_PUNCT.sub(r"\1\1", t)
    t = _SPACE_BEFORE_PUNCT.sub(r"\1", t)
    t = _SPACES.sub(" ", t).strip()
    return t


def is_empty(text: str) -> bool:
    return not _WORD.search(clean_text(text))


def remove_duplicate_cues(cues: list[dict]) -> tuple[list[dict], int]:
    """Drops exact-duplicate consecutive captions and 'rolling' captions where the next cue just extends the
    previous one (auto-caption style): the longer cue replaces the shorter prefix cue."""
    out: list[dict] = []
    removed = 0
    for c in cues:
        t = clean_text(c["text"]).lower()
        if out:
            p = clean_text(out[-1]["text"]).lower()
            if t == p:
                out[-1]["end"] = max(out[-1]["end"], c["end"])
                removed += 1
                continue
            if p and t.startswith(p):  # rolling caption: keep the extended text, keep the earlier start
                out[-1] = {**c, "start": out[-1]["start"], "text": c["text"]}
                removed += 1
                continue
        out.append(dict(c))
    return out, removed
