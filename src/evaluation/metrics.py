"""Evaluation metrics: point-wise regression, curve metrics and risk-segment localisation.

Risk ground truth (documented rule): a segment is a RISK segment if its local retention decline
drop = R(start) - R(end) is >= tau, where tau is the 80th percentile of positive drops on the TRAINING videos
(chosen on train only, never tuned on test). Predicted risk is either a model's risk head or the decline of its
predicted curve. Predicted risk REGIONS use a threshold chosen on the validation set (max F1), not the test set.
"""
import numpy as np
from scipy import stats


def regression_metrics(y_true, y_pred) -> dict:
    y, p = np.asarray(y_true, float), np.asarray(y_pred, float)
    err = p - y
    ss_res, ss_tot = float((err**2).sum()), float(((y - y.mean()) ** 2).sum())
    pear = float(stats.pearsonr(y, p)[0]) if y.std() > 0 and p.std() > 0 else float("nan")
    spear = float(stats.spearmanr(y, p)[0]) if y.std() > 0 and p.std() > 0 else float("nan")
    return dict(mae=float(np.abs(err).mean()), rmse=float(np.sqrt((err**2).mean())), r2=1 - ss_res / ss_tot if ss_tot > 0 else float("nan"),
                pearson=pear, spearman=spear)


def curve_metrics(true_curves: list[np.ndarray], pred_curves: list[np.ndarray], seg_seconds: list[np.ndarray]) -> dict:
    area, avg_err, max_err, corr, dcorr = [], [], [], [], []
    for t, p, d in zip(true_curves, pred_curves, seg_seconds):
        diff = np.abs(t - p)
        area.append(float((diff * d).sum()))  # percentage-points x seconds
        avg_err.append(float(diff.mean()))
        max_err.append(float(diff.max()))
        if len(t) > 2 and t.std() > 0 and p.std() > 0:
            corr.append(float(np.corrcoef(t, p)[0, 1]))
        td, pd_ = np.diff(t), np.diff(p)
        if len(td) > 2 and td.std() > 0 and pd_.std() > 0:
            dcorr.append(float(np.corrcoef(td, pd_)[0, 1]))
    return dict(area_between_curves=float(np.mean(area)), avg_pointwise_error=float(np.mean(avg_err)), max_error=float(np.mean(max_err)),
                curve_shape_corr=float(np.mean(corr)) if corr else float("nan"),
                decline_shape_corr=float(np.mean(dcorr)) if dcorr else float("nan"))


def risk_threshold_from_train(drops: np.ndarray, q: float = 0.8) -> float:
    pos = np.asarray(drops, float)
    pos = pos[pos > 0]
    return float(np.quantile(pos, q)) if len(pos) else 0.0


def risk_labels(drops: np.ndarray, tau: float) -> np.ndarray:
    return (np.asarray(drops, float) >= tau) & (np.asarray(drops, float) > 0)


def pred_risk_from_curve(curve: np.ndarray) -> np.ndarray:
    """Per-segment predicted decline of a predicted curve (last segment has no successor -> 0)."""
    d = np.zeros(len(curve))
    d[:-1] = np.maximum(curve[:-1] - curve[1:], 0.0)
    return d


def best_threshold_f1(scores: list[np.ndarray], labels: list[np.ndarray]) -> float:
    s, y = np.concatenate(scores), np.concatenate(labels)
    best, best_f1 = 0.0, -1.0
    for thr in np.unique(np.quantile(s, np.linspace(0.5, 0.99, 50))):
        pred = s >= thr
        tp = (pred & y).sum()
        f1 = 2 * tp / max(pred.sum() + y.sum(), 1)
        if f1 > best_f1:
            best, best_f1 = float(thr), f1
    return best


def chance_top_k(labels: list[np.ndarray], k: int) -> float:
    """Expected top-k hit rate of a RANDOM ranking (the reference every model must beat)."""
    vals = []
    for y in labels:
        n, m = len(y), int(y.sum())
        if m == 0:
            continue
        vals.append(1.0 - float(np.prod([(n - m - i) / (n - i) for i in range(min(k, n - m))])) if k <= n - m else 1.0)
    return float(np.mean(vals)) if vals else float("nan")


def risk_metrics(scores: list[np.ndarray], labels: list[np.ndarray], thr: float, seed: int = 0) -> dict:
    """Ties are broken RANDOMLY (a model with constant scores must perform at chance, not at 'earliest segment first')."""
    rng = np.random.default_rng(seed)
    top = {1: [], 3: [], 5: []}
    tp = fp = fn = 0
    ious = []
    for s, y in zip(scores, labels):
        jitter = rng.permutation(len(s))
        order = np.lexsort((jitter, -np.asarray(s, float)))  # primary: descending score, secondary: random
        if y.any():
            for k in top:
                top[k].append(bool(y[order[:k]].any()))
        pred = s >= thr
        tp += int((pred & y).sum()); fp += int((pred & ~y).sum()); fn += int((~pred & y).sum())
        union = (pred | y).sum()
        if union:
            ious.append(float((pred & y).sum() / union))
    base = float(np.mean(np.concatenate(labels)))
    precision = tp / max(tp + fp, 1)
    return dict(risk_recall=tp / max(tp + fn, 1), risk_precision=precision, top1_hit=float(np.mean(top[1])) if top[1] else float("nan"),
                top3_hit=float(np.mean(top[3])) if top[3] else float("nan"), top5_hit=float(np.mean(top[5])) if top[5] else float("nan"),
                chance_top1=chance_top_k(labels, 1), chance_top3=chance_top_k(labels, 3), chance_top5=chance_top_k(labels, 5),
                precision_lift=precision / base if base > 0 else float("nan"),  # precision / base rate: 1.0 = no better than flagging at random
                risk_iou=float(np.mean(ious)) if ious else float("nan"), n_risk_segments=int(sum(int(y.sum()) for y in labels)), base_rate=base)


# ---- position-adjusted ("excess") risk: anomalous declines beyond the typical decline at that point of the video -------------
def position_means(relative_position: np.ndarray, values: np.ndarray, bins: int = 20) -> np.ndarray:
    idx = np.minimum((np.asarray(relative_position) * bins).astype(int), bins - 1)
    m = np.array([values[idx == b].mean() if (idx == b).any() else np.nan for b in range(bins)])
    return np.where(np.isnan(m), np.nanmean(m), m)


def position_lookup(means: np.ndarray, relative_position: np.ndarray) -> np.ndarray:
    return means[np.minimum((np.asarray(relative_position) * len(means)).astype(int), len(means) - 1)]
