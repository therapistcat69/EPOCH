"""Explanations for the deep models (BiLSTM / Transformer / MLP): group ablation and Integrated Gradients.

Neither is a causal explanation. Attention weights are intentionally not used as importance.
"""
import numpy as np
import torch

from src.features import schema


def group_ablation(model, df_video, embs_video, target_idx: int, use_risk_head: bool) -> dict[str, float]:
    """Effect on the predicted decline at `target_idx` of replacing each feature group by the video's own median.
    Positive = the group's actual values INCREASE predicted risk relative to a neutral (median) version."""
    def predict_decline(d):
        ret, risk = model.predict_videos(d, embs_video)[d.video_id.iloc[0]]
        if use_risk_head and risk is not None:
            return float(max(risk[target_idx], 0.0))
        r = ret
        return float(max(r[target_idx] - r[min(target_idx + 1, len(r) - 1)], 0.0))

    base = predict_decline(df_video)
    out = {}
    for g, cols in schema.FEATURE_GROUPS.items():
        cols = [c for c in cols if c in df_video.columns]
        d = df_video.copy()
        d[cols] = d[cols].median().to_numpy()
        out[g] = base - predict_decline(d)
    return out


def integrated_gradients(model, df_video, embs_video, target_idx: int, steps: int = 32) -> np.ndarray:
    """Integrated Gradients of the predicted retention at `target_idx` w.r.t. the (handcrafted) segment inputs, baseline = 0
    (the standardised training mean). Returns (n_segments, n_handcrafted_features) attributions."""
    items = model._videos(df_video, embs_video)
    _, x, _, _ = items[0]
    n_hand = len(model.cols)
    x_t = torch.from_numpy(x).unsqueeze(0)
    base = torch.zeros_like(x_t)
    if model.use_embedding:
        base[..., n_hand:] = x_t[..., n_hand:]  # hold embeddings fixed; attribute handcrafted features only
    total = torch.zeros_like(x_t)
    model.net.eval()
    for a in np.linspace(1.0 / steps, 1.0, steps):
        inp = (base + a * (x_t - base)).clone().requires_grad_(True)
        pred, _ = model.net(inp, torch.ones(1, x_t.shape[1], dtype=torch.bool))
        pred[0, target_idx].backward()
        total += inp.grad
    ig = ((x_t - base) * total / steps)[0, :, :n_hand].detach().numpy()
    return ig
