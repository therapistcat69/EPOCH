"""Basic linguistic features of one segment's cleaned text (descriptive, not causal)."""
import math
import re

_WORD = re.compile(r"[\w']+", re.U)
_SENT = re.compile(r"[^.!?।]+[.!?।]*")

LINGUISTIC_COLUMNS = [
    "word_count", "character_count", "sentence_count", "average_sentence_length", "average_word_length",
    "words_per_second", "speaking_rate", "unique_word_ratio", "vocabulary_size", "lexical_diversity",
]


def words(text: str) -> list[str]:
    return [w.lower() for w in _WORD.findall(text or "")]


def sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT.findall(text or "") if _WORD.search(s)]


def linguistic_features(text: str, duration_seconds: float) -> dict:
    w = words(text)
    n = len(w)
    sents = sentences(text)
    uniq = len(set(w))
    dur = max(duration_seconds, 1e-6)
    return dict(
        word_count=n,
        character_count=len(text or ""),
        sentence_count=len(sents),
        average_sentence_length=n / len(sents) if sents else 0.0,
        average_word_length=sum(len(x) for x in w) / n if n else 0.0,
        words_per_second=n / dur,
        speaking_rate=n / dur * 60.0,  # words per minute
        unique_word_ratio=uniq / n if n else 0.0,  # type-token ratio
        vocabulary_size=uniq,
        lexical_diversity=uniq / math.sqrt(n) if n else 0.0,  # Guiraud's root TTR (less length-sensitive than TTR)
    )
