"""Evaluate retention predictions on a split of videos: point-wise, curve and risk-localisation metrics.

Segment 0 is excluded from point-wise metrics because R(0) = 100 by definition (it would inflate every score).
"""
import numpy as np
import pandas as pd

from src.evaluation import metrics as M


def per_video(df: pd.DataFrame, values: np.ndarray) -> dict[str, np.ndarray]:
    out, pos = {}, 0
    for vid, g in df.groupby("video_id", sort=False):
        out[vid] = np.asarray(values[pos : pos + len(g)], float)
        pos += len(g)
    return out


def evaluate_split(df: pd.DataFrame, pred_ret: np.ndarray, risk_scores: np.ndarray | None, tau: float, risk_thr: float | None,
                   excess: dict | None = None) -> dict:
    """df: rows of one split in (video, segment) order. pred_ret/risk_scores: one value per row.
    excess = dict(means=<train mean drop by position bin>, tau=<train 80th pct of positive excess>, thr=<val-chosen threshold or None>)."""
    y = df["retention_target"].to_numpy(float)
    keep = df["segment_id"].to_numpy() > 0
    out = dict(regression=M.regression_metrics(y[keep], np.asarray(pred_ret)[keep]))
    t_curves, p_curves, secs, scores, labels = [], [], [], [], []
    pv, tv = per_video(df, pred_ret), per_video(df, y)
    dv = per_video(df, df["drop_target"].to_numpy(float))
    durv = per_video(df, (df["end_time"] - df["start_time"]).to_numpy(float))
    rv = per_video(df, risk_scores) if risk_scores is not None else None
    for vid in pv:
        t_curves.append(tv[vid]); p_curves.append(pv[vid]); secs.append(durv[vid])
        scores.append(rv[vid] if rv is not None else M.pred_risk_from_curve(pv[vid]))
        labels.append(M.risk_labels(dv[vid], tau))
    out["curve"] = M.curve_metrics(t_curves, p_curves, secs)
    if risk_thr is not None:
        out["risk"] = M.risk_metrics(scores, labels, risk_thr)
    out["_scores"], out["_labels"] = scores, labels  # for threshold selection on validation
    if excess is not None:
        rel = per_video(df, df["relative_position"].to_numpy(float))
        exp = {v: M.position_lookup(excess["means"], rel[v]) for v in rel}
        ex_scores = [s - exp[v] for s, v in zip(scores, rel)]             # predicted decline beyond what position alone predicts
        ex_labels = [M.risk_labels(dv[v] - exp[v], excess["tau"]) for v in rel]  # actual decline beyond the typical position decline
        out["_ex_scores"], out["_ex_labels"] = ex_scores, ex_labels
        if excess.get("thr") is not None:
            out["risk_excess"] = M.risk_metrics(ex_scores, ex_labels, excess["thr"])
    return out


def strip_private(d: dict) -> dict:
    return {k: v for k, v in d.items() if not k.startswith("_")}


def flatten(prefix: str, d: dict) -> dict:
    out = {}
    for k, v in strip_private(d).items():
        if isinstance(v, dict):
            out.update(flatten(f"{prefix}{k}.", v))
        else:
            out[f"{prefix}{k}"] = v
    return out
