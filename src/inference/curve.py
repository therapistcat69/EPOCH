"""Conversion between segment-based predictions and YouTube Analytics' normalized time ratios (0.00 .. 1.00)."""
import numpy as np


def segments_to_normalized(starts: np.ndarray, retention: np.ndarray, duration: float, n_points: int = 101) -> tuple[np.ndarray, np.ndarray]:
    """Retention is defined at segment START times; the last point (ratio 1.0) holds the last predicted value.
    Returns (time_ratio grid, retention on that grid)."""
    ratios = np.linspace(0.0, 1.0, n_points)
    x = np.asarray(starts, float) / max(duration, 1e-9)
    xs = np.append(x, 1.0)
    ys = np.append(retention, retention[-1])
    return ratios, np.interp(ratios, xs, ys)


def normalized_to_segments(ratios: np.ndarray, values: np.ndarray, starts: np.ndarray, duration: float) -> np.ndarray:
    """Inverse direction: sample a normalized (e.g. YouTube Analytics) curve at segment start times."""
    return np.interp(np.asarray(starts, float) / max(duration, 1e-9), ratios, values)
