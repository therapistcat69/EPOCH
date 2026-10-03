"""Topic-change features from embeddings.

    topic_change_score = 1 - cos( mean(emb[i-2 .. i-1]),  mean(emb[i .. i+1]) )      (look-ahead is fine: the full
                                                                                       transcript is known pre-publication)
    semantic_shift     = 1 - cos(emb[i], emb[i-1])
"""
import numpy as np

TOPIC_COLUMNS = ["topic_change_score", "semantic_shift", "similarity_with_previous_segment"]


def topic_features(emb: np.ndarray, sim: dict, empty: np.ndarray) -> list[dict]:
    n = len(emb)
    out = []
    for i in range(n):
        if empty[i] or i == 0:
            out.append(dict(topic_change_score=0.0, semantic_shift=0.0, similarity_with_previous_segment=float(sim["sim_prev"][i])))
            continue
        before = [j for j in range(max(0, i - 2), i) if not empty[j]]
        after = [j for j in range(i, min(n, i + 2)) if not empty[j]]
        if not before or not after:
            score = 0.0
        else:
            a, b = emb[before].mean(0), emb[after].mean(0)
            na, nb = np.linalg.norm(a), np.linalg.norm(b)
            score = float(np.clip(1.0 - (a @ b) / (na * nb), 0, 1)) if na and nb else 0.0
        out.append(dict(topic_change_score=score, semantic_shift=float(np.clip(1.0 - sim["sim_prev"][i], 0, 1)),
                        similarity_with_previous_segment=float(sim["sim_prev"][i])))
    return out
