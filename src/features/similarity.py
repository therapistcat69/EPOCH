"""Shared embedding-similarity context used by the repetition, information-density and topic modules."""
import numpy as np


def similarity_context(emb: np.ndarray, empty: np.ndarray, recent: int = 3) -> dict:
    """emb: (n, d) L2-normalised segment embeddings; empty: (n,) bool (no captions in that window).
    Returns per-segment arrays (empty segments get 0 similarity and are ignored as neighbours)."""
    n = len(emb)
    S = emb @ emb.T if n else np.zeros((0, 0), dtype=np.float32)
    S = np.clip(S, -1.0, 1.0)
    valid = ~empty
    sim_prev = np.zeros(n)
    sim_recent_mean = np.zeros(n)
    sim_earlier_max = np.zeros(n)  # earlier, non-adjacent segments
    sim_any_earlier_max = np.zeros(n)  # all earlier segments (incl. adjacent) -> novelty
    for i in range(n):
        if empty[i]:
            continue
        if i >= 1 and valid[i - 1]:
            sim_prev[i] = S[i, i - 1]
        rec = [j for j in range(max(0, i - recent), i) if valid[j]]
        if rec:
            sim_recent_mean[i] = float(np.mean(S[i, rec]))
        far = [j for j in range(0, i - 1) if valid[j]]
        if far:
            sim_earlier_max[i] = float(np.max(S[i, far]))
        anyj = [j for j in range(0, i) if valid[j]]
        if anyj:
            sim_any_earlier_max[i] = float(np.max(S[i, anyj]))
    return dict(S=S, sim_prev=sim_prev, sim_recent_mean=sim_recent_mean, sim_earlier_max=sim_earlier_max,
                sim_any_earlier_max=sim_any_earlier_max)
