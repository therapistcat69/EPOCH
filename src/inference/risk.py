"""Risk-region detection from predicted local declines.

    predicted_drop_i = max(R^_i - R^_{i+1}, 0)   (or a model's own decline/risk head)
    risk_score_i     = clip(predicted_drop_i / (2 * tau), 0, 1)       tau = 80th percentile of positive drops in the TRAIN set
A region is a run of consecutive segments whose predicted drop >= threshold (threshold picked on VALIDATION data).
risk_score is a monotone rescaling for display, NOT a calibrated probability.
"""
import numpy as np


def detect_regions(starts: np.ndarray, ends: np.ndarray, drops: np.ndarray, threshold: float, tau: float, top_n: int = 5, pad_segments: int = 0) -> list[dict]:
    flagged = drops >= threshold
    regions, i, n = [], 0, len(drops)
    while i < n:
        if not flagged[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and flagged[j + 1]:
            j += 1
        a, b = max(0, i - pad_segments), min(n - 1, j + pad_segments)
        peak = float(drops[i : j + 1].max())
        regions.append(dict(start=float(starts[a]), end=float(ends[b]), idx_start=int(i), idx_end=int(j), peak_drop=peak,
                            total_drop=float(drops[i : j + 1].sum()), risk_score=float(np.clip(peak / max(2 * tau, 1e-9), 0, 1))))
        i = j + 1
    # rank by the actual predicted decline: risk_score saturates at 1.0 (display scale) and would tie unequal regions
    regions.sort(key=lambda r: (-r["peak_drop"], r["start"]))
    return regions[:top_n]
