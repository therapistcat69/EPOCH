"""Title / content alignment.

    title_similarity(i)   = cosine(title_embedding, segment_embedding_i)
    promise_gap_seconds   = start time of the first segment whose title_similarity >= max(0.30, 0.65 * max_i title_similarity)
                            (the video duration if no segment qualifies)

The promise gap is a MEASURABLE CONTENT FEATURE of how far into the video the content starts addressing the title's
main semantic promise. The first semantically related sentence is not proof of "promise fulfilment".
"""
import numpy as np

TITLE_COLUMNS = ["title_similarity", "promise_gap_seconds", "is_after_promise"]
MIN_SIM, REL_SIM = 0.30, 0.65


def title_features(title_emb: np.ndarray, emb: np.ndarray, starts: list[float], empty: np.ndarray, duration: float) -> list[dict]:
    if len(emb) == 0:
        return []
    sims = np.clip(emb @ title_emb, -1.0, 1.0)
    sims = np.where(empty, 0.0, sims)
    thr = max(MIN_SIM, REL_SIM * float(sims.max()))
    gap = next((starts[i] for i in range(len(sims)) if sims[i] >= thr), duration)
    return [dict(title_similarity=float(s), promise_gap_seconds=float(gap), is_after_promise=int(starts[i] >= gap)) for i, s in enumerate(sims)]
