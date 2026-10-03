"""Interpretable information-density / novelty features. NOT a universal definition of information density.

Exact formulas (all in [0, 1], empty segments -> 0):

    semantic_novelty      = 1 - max cosine similarity of the segment embedding to ANY earlier segment (first segment = 1)
    novelty_vs_recent     = 1 - mean cosine similarity to the previous 3 segments
    new_term_ratio        = (# content-word types not seen earlier in the video) / (# content-word types in the segment)
    entity_density        = (# capitalised mid-sentence tokens + # numbers) / words        [heuristic NER, no spaCy]
    content_word_ratio    = content words / words
    embedding_distance_prev = 1 - cosine(segment, previous segment)

    information_density   = clip( 0.35 * semantic_novelty
                                + 0.25 * new_term_ratio
                                + 0.20 * min(lexical_diversity / 5, 1)
                                + 0.10 * min(entity_density * 5, 1)
                                + 0.10 * content_word_ratio , 0, 1)
The weights are fixed a-priori (not fitted to retention) so the feature stays interpretable.
"""
import re

import numpy as np

from src.features.linguistic import words
from src.features.stopwords import STOPWORDS

INFORMATION_COLUMNS = [
    "semantic_novelty", "novelty_vs_recent_context", "new_term_ratio", "unique_concepts", "named_entity_density",
    "content_word_ratio", "embedding_distance_prev", "information_density",
]
_CAP = re.compile(r"(?<![.!?]\s)(?<!^)\b[A-Z][a-z]{2,}\b")


def information_features(texts: list[str], lex_div: list[float], sim: dict, empty: np.ndarray) -> list[dict]:
    seen: set[str] = set()
    out = []
    for i, text in enumerate(texts):
        w = words(text)
        content = [x for x in w if x not in STOPWORDS and len(x) > 2]
        types = set(content)
        if empty[i]:
            out.append({c: 0.0 for c in INFORMATION_COLUMNS})
            continue
        new_terms = types - seen
        seen |= types
        novelty = 1.0 if i == 0 else float(1.0 - sim["sim_any_earlier_max"][i])
        novelty = float(np.clip(novelty, 0, 1))
        recent_nov = float(np.clip(1.0 - sim["sim_recent_mean"][i], 0, 1)) if i > 0 else 1.0
        n_ent = len(_CAP.findall(text or "")) + sum(1 for x in w if x.isdigit())
        ent_density = n_ent / max(len(w), 1)
        cwr = len(content) / max(len(w), 1)
        new_ratio = len(new_terms) / max(len(types), 1)
        dens = 0.35 * novelty + 0.25 * new_ratio + 0.20 * min(lex_div[i] / 5.0, 1.0) + 0.10 * min(ent_density * 5, 1.0) + 0.10 * cwr
        out.append(dict(semantic_novelty=novelty, novelty_vs_recent_context=recent_nov, new_term_ratio=new_ratio,
                        unique_concepts=len(new_terms), named_entity_density=ent_density, content_word_ratio=cwr,
                        embedding_distance_prev=float(1.0 - sim["sim_prev"][i]) if i > 0 else 1.0,
                        information_density=float(np.clip(dens, 0, 1))))
    return out
