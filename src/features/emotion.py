"""Sentiment and emotion features for gaming language.

Two lightweight scorers are provided and compared in `src/evaluation/emotion_eval.py`:
  * VADER (general-purpose sentiment)            -> sentiment_positive / negative / neutral
  * a gaming emotion lexicon (rule-based)        -> joy, surprise, fear, anger, sadness, excitement
A generic sentiment model is NOT assumed to fit gaming language ("this boss is brutal" is praise, "I died" is
neutral-negative but often comedic). Known limitation: both are lexical and miss sarcasm and context.
"""
import math
import re

from src.features.linguistic import words

EMOTIONS = ("joy", "surprise", "fear", "anger", "sadness", "excitement")
EMOTION_COLUMNS = ["sentiment_positive", "sentiment_negative", "sentiment_neutral", *[f"emotion_{e}" for e in EMOTIONS], "emotional_intensity"]

LEXICON: dict[str, list[str]] = {
    "joy": ["love", "awesome", "great", "amazing", "beautiful", "happy", "fun", "favourite", "favorite", "satisfying", "proud", "nice", "glad", "enjoy", "enjoyed"],
    "surprise": ["wait", "whoa", "wow", "unexpected", "suddenly", "no way", "did not expect", "didn't expect", "cannot believe", "can't believe", "what", "seriously", "shock"],
    "fear": ["scared", "panic", "afraid", "terrified", "nervous", "danger", "almost gone", "careful", "dying", "tense", "one wrong move", "closer", "barely"],
    "anger": ["unfair", "rage", "angry", "hate", "stupid", "annoying", "trash", "cheating", "frustrating", "frustrated", "ridiculous", "cheap"],
    "sadness": ["died", "dead", "lost", "sad", "sorry", "unfortunately", "failed", "hurts", "miss", "back to the start", "gave up"],
    "excitement": ["let's go", "lets go", "yes", "insane", "incredible", "clutch", "epic", "crazy", "hype", "finally", "we did it", "absolutely", "first try", "we got it", "i did it"],
}
_PATTERNS = {e: re.compile(r"\b(" + "|".join(re.escape(t) for t in toks) + r")\b", re.I) for e, toks in LEXICON.items()}

_vader = None


def _get_vader():
    global _vader
    if _vader is None:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        _vader = SentimentIntensityAnalyzer()
    return _vader


def lexicon_emotions(text: str) -> dict:
    n = max(len(words(text)), 1)
    out = {}
    for e, pat in _PATTERNS.items():
        hits = len(pat.findall(text or ""))
        out[e] = min(hits / max(n / 20.0, 1.0), 1.0)  # hits per ~20 words, capped at 1
    out["exclamation_boost"] = min((text or "").count("!") / max(n / 20.0, 1.0), 1.0)
    return out


def vader_sentiment(text: str) -> dict:
    s = _get_vader().polarity_scores(text or "")
    return dict(positive=s["pos"], negative=s["neg"], neutral=s["neu"], compound=s["compound"])


def emotion_features(text: str) -> dict:
    v = vader_sentiment(text)
    lex = lexicon_emotions(text)
    # smooth saturation (1 - exp(-x)) instead of a hard cap, which saturated at 1.0 for most segments
    intensity = 1.0 - math.exp(-0.8 * (sum(lex[e] for e in EMOTIONS) + 0.5 * lex["exclamation_boost"]))
    return {
        "sentiment_positive": v["positive"], "sentiment_negative": v["negative"], "sentiment_neutral": v["neutral"],
        **{f"emotion_{e}": lex[e] for e in EMOTIONS}, "emotional_intensity": intensity,
    }
