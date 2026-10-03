"""Repetition features: lexical (repeated words/phrases/n-grams) AND semantic (embedding similarity).

Semantic similarity is what catches paraphrases ("AI will change development" vs "software development will be
transformed by AI"), which exact string matching misses.

    redundant_information_score = clip(0.5 * sim_earlier_max + 0.3 * sim_recent_mean + 0.2 * ngram_repetition_prev, 0, 1)
"""
from collections import Counter

import numpy as np

from src.features.linguistic import words
from src.features.stopwords import STOPWORDS

REPETITION_COLUMNS = [
    "repeated_word_ratio", "repeated_phrase_ratio", "ngram_repetition_prev", "similarity_with_recent_context",
    "similarity_with_earlier_segments", "redundant_information_score",
]


def _ngrams(w: list[str], n: int) -> list[tuple]:
    return [tuple(w[i : i + n]) for i in range(len(w) - n + 1)]


def repetition_features(texts: list[str], sim: dict, empty: np.ndarray) -> list[dict]:
    toks = [words(t) for t in texts]
    out = []
    for i, w in enumerate(toks):
        content = [x for x in w if x not in STOPWORDS and len(x) > 2]
        c = Counter(content)
        rep_words = sum(v for v in c.values() if v > 1) / max(len(content), 1)
        bi = _ngrams(w, 2)
        cb = Counter(bi)
        rep_phr = sum(v for v in cb.values() if v > 1) / max(len(bi), 1)
        prev = set()
        for j in range(max(0, i - 4), i):
            prev.update(_ngrams(toks[j], 3))
        tri = _ngrams(w, 3)
        ng_prev = (sum(1 for t in tri if t in prev) / len(tri)) if tri else 0.0
        recent, earlier = float(sim["sim_recent_mean"][i]), float(sim["sim_earlier_max"][i])
        score = 0.0 if empty[i] else float(np.clip(0.5 * earlier + 0.3 * recent + 0.2 * ng_prev, 0, 1))
        out.append(dict(repeated_word_ratio=rep_words, repeated_phrase_ratio=rep_phr, ngram_repetition_prev=ng_prev,
                        similarity_with_recent_context=recent, similarity_with_earlier_segments=earlier,
                        redundant_information_score=score))
    return out
