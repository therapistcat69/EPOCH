"""Build the processed segment-level dataset (features + embeddings + targets) for one configuration.

Targets (synthetic labels, from data/synthetic):
    retention_target = R(segment start)                    in percent; first segment = 100
    drop_target      = R(segment start) - R(segment end)    local decline within the segment (can be negative on re-watch bumps)
Real data (data/real) would use the same format with actual YouTube retention resampled onto the same grid.
"""
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from src import config
from src.features.pipeline import build_video_features


def retention_at(values: list[float] | np.ndarray, t: float) -> float:
    """Linear interpolation of a 1-second-resolution retention curve at time t (seconds)."""
    v = np.asarray(values, dtype=float)
    t = min(max(t, 0.0), len(v) - 1)
    return float(np.interp(t, np.arange(len(v)), v))


def processed_path(segment_seconds: int, embedder_name: str, version: str = config.DATASET_VERSION) -> Path:
    return config.processed_dir(version) / f"seg{int(segment_seconds)}_{embedder_name}.joblib"


def build_dataset(segment_seconds: int, embedder, version: str = config.DATASET_VERSION, limit: int | None = None, force: bool = False) -> dict:
    path = processed_path(segment_seconds, embedder.name, version)
    if path.exists() and not force and limit is None:
        return joblib.load(path)
    raw_dir, syn_dir = config.raw_dir(version), config.synthetic_dir(version)
    retention = json.loads((syn_dir / "retention.json").read_text(encoding="utf-8"))["videos"]
    manifest = pd.read_csv(syn_dir / "manifest.csv")
    tables, embs, title_embs, curves = [], {}, {}, {}
    for vid in manifest.video_id.tolist()[:limit]:
        v = json.loads((raw_dir / "videos" / f"{vid}.json").read_text(encoding="utf-8"))
        vf = build_video_features(vid, v["title"], v["description"], v["duration"], v["segments"], embedder, segment_seconds)
        R = retention[vid]["values"]
        t = vf.table
        t["retention_target"] = [retention_at(R, s) for s in t["start_time"]]
        t["drop_target"] = [retention_at(R, s) - retention_at(R, e) for s, e in zip(t["start_time"], t["end_time"])]
        t.loc[t.index[0], "retention_target"] = 100.0
        tables.append(t)
        embs[vid], title_embs[vid], curves[vid] = vf.embeddings, vf.title_embedding, np.asarray(R, dtype=np.float32)
    if hasattr(embedder, "save"):
        embedder.save()
    df = pd.concat(tables, ignore_index=True)
    out = dict(df=df, embeddings=embs, title_embeddings=title_embs, curves=curves, segment_seconds=int(segment_seconds),
               embedder=embedder.name, embedding_dim=int(embedder.dim), dataset_version=version,
               feature_schema_version=config.FEATURE_SCHEMA_VERSION, data_mode=config.MODE_SYNTHETIC)
    if limit is None:
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(out, path)
    return out
