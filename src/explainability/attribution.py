"""Model-based explanations of predicted risk. These are model attributions - NOT causal reasons.

* Tree models (Random Forest / XGBoost): SHAP TreeExplainer (exact for trees).
* Deep models: feature-GROUP ablation (replace a group with the video's own median) - an input-perturbation view -
  and Integrated Gradients (see integrated_gradients). Attention weights are NOT used as importance.
For a risk region, contributions explain the predicted local decline: for delta-target models that is the SHAP value of
the segment; for absolute-target models it is shap_i - shap_{i+1} (SHAP is additive, so differences are valid).
"""
import numpy as np
import pandas as pd

from src.features import schema


def _group_features(cols: list[str]) -> dict[str, list[int]]:
    groups: dict[str, list[int]] = {}
    for i, c in enumerate(cols):
        groups.setdefault(schema.group_of(c), []).append(i)
    return groups


def shap_values_tree(model, df: pd.DataFrame, emb: np.ndarray | None) -> tuple[np.ndarray, list[str]]:
    """SHAP values (n_rows, n_features) of a FlatRetentionModel's underlying tree model."""
    import shap

    Xm = model._matrix(df, emb)
    X = Xm.toarray() if hasattr(Xm, "toarray") else Xm
    tree_model = model.model
    # XGBoost predicts with the early-stopped best iteration; SHAP must explain exactly those trees or the attributions
    # would not add up to the prediction (caught by tests/test_models_and_inference.py::test_shap_values_are_additive).
    best = getattr(tree_model, "best_iteration", None)
    if model.kind == "xgb" and best is not None:
        explainer = shap.TreeExplainer(tree_model.get_booster()[: int(best) + 1])
    else:
        explainer = shap.TreeExplainer(tree_model)
    return np.asarray(explainer.shap_values(X)), model.feature_names()


def aggregate_to_features(values: np.ndarray, names: list[str]) -> tuple[np.ndarray, list[str]]:
    """Collapse embedding dimensions and TF-IDF terms into single 'embedding' / 'tfidf' columns for readable explanations."""
    keep = [i for i, n in enumerate(names) if not (n.startswith("emb_") or n.startswith("tfidf_"))]
    out_names = [names[i] for i in keep]
    out = values[:, keep]
    extra, extra_names = [], []
    for prefix, label in (("emb_", "semantic_embedding"), ("tfidf_", "text_tfidf")):
        idx = [i for i, n in enumerate(names) if n.startswith(prefix)]
        if idx:
            extra.append(values[:, idx].sum(1, keepdims=True))
            extra_names.append(label)
    if extra:
        out = np.concatenate([out] + extra, axis=1)
        out_names += extra_names
    return out, out_names


def global_importance(values: np.ndarray, names: list[str]) -> pd.DataFrame:
    agg, an = aggregate_to_features(values, names)
    return pd.DataFrame(dict(feature=an, mean_abs_shap=np.abs(agg).mean(0), group=[schema.group_of(n) for n in an])).sort_values("mean_abs_shap", ascending=False)


def permutation_group_importance(predict_fn, df: pd.DataFrame, y: np.ndarray, groups: dict[str, list[str]], n_repeats: int = 3, seed: int = 0) -> dict[str, float]:
    """Increase in MAE when a feature GROUP's columns are shuffled across rows (feature-group permutation importance)."""
    rng = np.random.default_rng(seed)
    base = float(np.abs(predict_fn(df) - y).mean())
    out = {}
    for g, cols in groups.items():
        cols = [c for c in cols if c in df.columns]
        if not cols:
            continue
        deltas = []
        for _ in range(n_repeats):
            d = df.copy()
            perm = rng.permutation(len(d))
            d[cols] = d[cols].to_numpy()[perm]
            deltas.append(float(np.abs(predict_fn(d) - y).mean()) - base)
        out[g] = float(np.mean(deltas))
    return out


def risk_contributions(shap_vals: np.ndarray, names: list[str], idx: int, target: str) -> tuple[np.ndarray, list[str]]:
    """Per-feature contribution toward predicted risk (decline) for the segment at row `idx` (video-local order)."""
    agg, an = aggregate_to_features(shap_vals, names)
    if target == "drop_target":
        return agg[idx], an
    nxt = min(idx + 1, len(agg) - 1)
    return agg[idx] - agg[nxt], an  # SHAP additivity: decline = R_i - R_{i+1}


def factors_for_segment(contrib: np.ndarray, names: list[str], row: pd.Series, video_median: pd.Series, top_k: int = 4) -> list[dict]:
    """Top features pushing risk UP, labelled by whether the segment is high/low relative to the rest of the video."""
    order = np.argsort(-contrib)
    out = []
    for i in order:
        if contrib[i] <= 0 or len(out) >= top_k:
            break
        f = names[i]
        if f in ("semantic_embedding", "text_tfidf"):
            out.append(dict(feature=f, group=schema.group_of(f) if f in schema.FEATURE_GROUPS else ("embedding" if f == "semantic_embedding" else "text"),
                            contribution=float(contrib[i]), direction="high", label="text content (embedding/TF-IDF)"))
            continue
        high = bool(row.get(f, 0) >= video_median.get(f, 0))
        out.append(dict(feature=f, group=schema.group_of(f), contribution=float(contrib[i]), direction="high" if high else "low",
                        label=schema.label_factor(f, high)))
    return out


def explanation_text(start: float, end: float, factors: list[dict]) -> str:
    if not factors:
        return "No single feature stands out for this segment in the model's attribution."
    parts = [f["label"] for f in factors[:3]]
    return ("Compared with the rest of this video, the model's attribution for this segment is driven by: " + "; ".join(parts) +
            ". This is a model-based explanation, not a causal reason.")
