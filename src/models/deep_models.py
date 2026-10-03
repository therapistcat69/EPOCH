"""PyTorch models: MLP (per segment), BiLSTM and compact Temporal Transformer (sequence -> retention sequence).

Inputs per segment: standardised handcrafted features + (optional) sentence embedding + relative position.
Sequence models output the ENTIRE retention curve for a video (any number of segments) and, if multi_task=True, a
second head predicting the local decline (risk). The Transformer is deliberately small (dataset is small).
"""
import math
import random
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import torch
import torch.nn as nn

from src import config
from src.features import schema


def set_seed(seed: int) -> None:
    random.seed(seed); np.random.seed(seed); torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


class Standardizer:
    def fit(self, x: np.ndarray):
        self.mu, self.sd = x.mean(0), x.std(0) + 1e-6
        return self

    def transform(self, x: np.ndarray) -> np.ndarray:
        return ((x - self.mu) / self.sd).astype(np.float32)


def _encoder(d_in: int, d_model: int, dropout: float) -> nn.Module:
    return nn.Sequential(nn.Linear(d_in, d_model), nn.LayerNorm(d_model), nn.GELU(), nn.Dropout(dropout))


class MLPNet(nn.Module):
    def __init__(self, d_in: int, hidden=(256, 128), dropout=0.2, multi_task=False):
        super().__init__()
        layers, d = [], d_in
        for h in hidden:
            layers += [nn.Linear(d, h), nn.GELU(), nn.Dropout(dropout)]
            d = h
        self.body = nn.Sequential(*layers)
        self.ret = nn.Linear(d, 1)
        self.risk = nn.Linear(d, 1) if multi_task else None

    def forward(self, x, mask=None):
        h = self.body(x)
        return torch.sigmoid(self.ret(h)).squeeze(-1), (self.risk(h).squeeze(-1) if self.risk is not None else None)


class BiLSTMNet(nn.Module):
    def __init__(self, d_in: int, d_model=128, layers=2, dropout=0.2, multi_task=False):
        super().__init__()
        self.enc = _encoder(d_in, d_model, dropout)
        self.rnn = nn.LSTM(d_model, d_model, num_layers=layers, batch_first=True, bidirectional=True, dropout=dropout if layers > 1 else 0.0)
        self.ret = nn.Linear(2 * d_model, 1)
        self.risk = nn.Linear(2 * d_model, 1) if multi_task else None

    def forward(self, x, mask=None):
        h, _ = self.rnn(self.enc(x))
        return torch.sigmoid(self.ret(h)).squeeze(-1), (self.risk(h).squeeze(-1) if self.risk is not None else None)


class TemporalTransformerNet(nn.Module):
    """segment features -> projection -> positional encoding -> compact Transformer encoder -> heads."""

    def __init__(self, d_in: int, d_model=128, layers=2, heads=4, dropout=0.2, multi_task=False, max_len=512):
        super().__init__()
        self.proj = _encoder(d_in, d_model, dropout)
        pe = torch.zeros(max_len, d_model)
        pos = torch.arange(max_len).unsqueeze(1)
        div = torch.exp(torch.arange(0, d_model, 2) * (-math.log(10000.0) / d_model))
        pe[:, 0::2], pe[:, 1::2] = torch.sin(pos * div), torch.cos(pos * div)
        self.register_buffer("pe", pe)
        layer = nn.TransformerEncoderLayer(d_model, heads, dim_feedforward=2 * d_model, dropout=dropout, batch_first=True, norm_first=True, activation="gelu")
        self.encoder = nn.TransformerEncoder(layer, layers)
        self.ret = nn.Linear(d_model, 1)
        self.risk = nn.Linear(d_model, 1) if multi_task else None

    def forward(self, x, mask=None):
        h = self.proj(x) + self.pe[: x.shape[1]].unsqueeze(0)
        h = self.encoder(h, src_key_padding_mask=(~mask) if mask is not None else None)
        return torch.sigmoid(self.ret(h)).squeeze(-1), (self.risk(h).squeeze(-1) if self.risk is not None else None)


def make_net(arch: str, d_in: int, cfg: dict) -> nn.Module:
    mt = cfg.get("multi_task", False)
    if arch == "mlp":
        return MLPNet(d_in, tuple(cfg.get("hidden", (256, 128))), cfg.get("dropout", 0.2), mt)
    if arch == "bilstm":
        return BiLSTMNet(d_in, cfg.get("d_model", 128), cfg.get("layers", 2), cfg.get("dropout", 0.2), mt)
    if arch == "transformer":
        return TemporalTransformerNet(d_in, cfg.get("d_model", 128), cfg.get("layers", 2), cfg.get("heads", 4), cfg.get("dropout", 0.2), mt)
    raise ValueError(arch)


class DeepRetentionModel:
    """Wraps a torch net with its preprocessing so it can be saved/loaded as one unit."""

    def __init__(self, arch: str = "transformer", use_embedding: bool = True, seed: int = config.SEED, cfg: dict | None = None):
        self.arch, self.use_embedding, self.seed, self.cfg = arch, use_embedding, seed, dict(cfg or {})
        self.name = f"{arch}{'_emb' if use_embedding else ''}{'_mt' if self.cfg.get('multi_task') else ''}"
        self.cols = list(schema.PRE_PUBLICATION_FEATURES)
        schema.assert_pre_publication(self.cols)
        self.scaler = None
        self.net = None
        self.history: list[dict] = []

    # -- data
    def _videos(self, df: pd.DataFrame, embs: dict, fit_scaler: bool = False):
        X = df[self.cols].to_numpy(dtype=np.float32)
        if fit_scaler:
            self.scaler = Standardizer().fit(X)
        Xs = self.scaler.transform(X)
        out, pos = [], 0
        for vid, g in df.groupby("video_id", sort=False):
            n = len(g)
            x = Xs[pos : pos + n]
            if self.use_embedding:
                x = np.concatenate([x, embs[vid][g.segment_id.to_numpy()]], axis=1)
            y = g["retention_target"].to_numpy(np.float32) / 100.0 if "retention_target" in g else np.zeros(n, np.float32)
            dr = g["drop_target"].to_numpy(np.float32) / 10.0 if "drop_target" in g else np.zeros(n, np.float32)
            out.append((vid, x.astype(np.float32), y, dr))
            pos += n
        return out

    @staticmethod
    def _batch(items, device):
        L = max(len(i[1]) for i in items)
        d = items[0][1].shape[1]
        X = torch.zeros(len(items), L, d); Y = torch.zeros(len(items), L); D = torch.zeros(len(items), L); M = torch.zeros(len(items), L, dtype=torch.bool)
        for k, (_, x, y, dr) in enumerate(items):
            n = len(x)
            X[k, :n], Y[k, :n], D[k, :n], M[k, :n] = torch.from_numpy(x), torch.from_numpy(y), torch.from_numpy(dr), True
        return X.to(device), Y.to(device), D.to(device), M.to(device)

    # -- loss
    def _loss(self, pred, risk, Y, D, M):
        kind = self.cfg.get("loss", "mae")
        diff = (pred - Y)[M]
        if kind == "mse":
            point = (diff**2).mean()
        elif kind == "huber":
            point = nn.functional.huber_loss(pred[M], Y[M], delta=0.05)
        else:
            point = diff.abs().mean()
        loss = point
        lam_curve = self.cfg.get("curve_loss", 0.0)
        if lam_curve and pred.shape[1] > 1:  # shape loss: match the first differences of the curve
            dm = M[:, 1:] & M[:, :-1]
            loss = loss + lam_curve * ((pred[:, 1:] - pred[:, :-1]) - (Y[:, 1:] - Y[:, :-1])).abs()[dm].mean()
        if risk is not None:
            loss = loss + self.cfg.get("risk_weight", 0.5) * nn.functional.huber_loss(risk[M], D[M], delta=0.2)
        return loss

    # -- fit
    def fit(self, df_tr, embs_tr, df_va, embs_va, epochs: int = 120, lr: float = 1e-3, weight_decay: float = 1e-4, batch_videos: int = 16, patience: int = 15):
        set_seed(self.seed)
        tr = self._videos(df_tr, embs_tr, fit_scaler=True)
        va = self._videos(df_va, embs_va)
        d_in = tr[0][1].shape[1]
        self.net = make_net(self.arch, d_in, self.cfg)
        opt = torch.optim.AdamW(self.net.parameters(), lr=lr, weight_decay=weight_decay)
        flat = self.arch == "mlp"
        best, best_state, bad = float("inf"), None, 0
        rng = np.random.default_rng(self.seed)
        for ep in range(epochs):
            self.net.train()
            order = rng.permutation(len(tr))
            tr_loss = 0.0
            for i in range(0, len(order), batch_videos):
                X, Y, D, M = self._batch([tr[j] for j in order[i : i + batch_videos]], "cpu")
                pred, risk = self.net(X, M)
                loss = self._loss(pred, risk, Y, D, M)
                opt.zero_grad(); loss.backward()
                nn.utils.clip_grad_norm_(self.net.parameters(), 1.0)
                opt.step()
                tr_loss += float(loss) * len(order[i : i + batch_videos])
            self.net.eval()
            with torch.no_grad():
                X, Y, D, M = self._batch(va, "cpu")
                pred, risk = self.net(X, M)
                val = float((pred - Y).abs()[M].mean()) * 100.0  # validation MAE in percentage points
            self.history.append(dict(epoch=ep + 1, train_loss=tr_loss / len(tr), val_mae=val))
            if val < best - 1e-4:
                best, bad = val, 0
                best_state = {k: v.clone() for k, v in self.net.state_dict().items()}
            else:
                bad += 1
                if bad >= patience:
                    break
        self.net.load_state_dict(best_state)
        self.best_val_mae = best
        return self

    # -- predict
    def predict_videos(self, df: pd.DataFrame, embs: dict) -> dict:
        """Returns {video_id: (retention_percent (n,), risk_score (n,) or None)} in segment order."""
        self.net.eval()
        out = {}
        with torch.no_grad():
            for vid, x, y, dr in self._videos(df, embs):
                X = torch.from_numpy(x).unsqueeze(0)
                M = torch.ones(1, len(x), dtype=torch.bool)
                pred, risk = self.net(X, M)
                out[vid] = (pred[0].numpy() * 100.0, (risk[0].numpy() * 10.0) if risk is not None else None)
        return out

    def n_params(self) -> int:
        return int(sum(p.numel() for p in self.net.parameters()))

    def save(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        torch.save(self.net.state_dict(), path / "model.pt")
        joblib.dump(self.scaler, path / "scaler.pkl")
        (path / "net_config.json").write_text(__import__("json").dumps(dict(arch=self.arch, use_embedding=self.use_embedding, seed=self.seed, cfg=self.cfg, cols=self.cols,
                                                                         d_in=int(next(iter(self.net.parameters())).shape[1]))), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "DeepRetentionModel":
        import json
        c = json.loads((path / "net_config.json").read_text(encoding="utf-8"))
        m = cls(c["arch"], c["use_embedding"], c["seed"], c["cfg"])
        m.cols, m.scaler = c["cols"], joblib.load(path / "scaler.pkl")
        m.net = make_net(c["arch"], c["d_in"], c["cfg"])
        m.net.load_state_dict(torch.load(path / "model.pt", map_location="cpu"))
        m.net.eval()
        return m
