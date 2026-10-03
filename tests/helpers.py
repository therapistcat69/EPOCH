"""Shared helpers: a tiny synthetic dataset + trained artifact built in a temp dir with the (non-semantic) hashing embedder.
Only pipeline mechanics are tested with it; reported results always use the real sentence-transformer embeddings."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src import config
from src.data_generation.generate import generate_dataset
from src.embeddings import HashingEmbedder
from src.features.pipeline import build_video_features
from src.training.dataset import retention_at
from src.training.splits import family_splits

EMB = HashingEmbedder(128)


def tiny_dataset(root: Path, seg: int = 15, families: int = 3, per_family: int = 2):
    """Returns (df, embeddings, manifest, assign). 10 archetypes x families x per_family videos."""
    generate_dataset(seed=5, families=families, per_family=per_family, version="synthetic_test", out_root=root)
    raw, syn = root / "raw" / "synthetic_test", root / "synthetic" / "synthetic_test"
    manifest = pd.read_csv(syn / "manifest.csv")
    ret = json.loads((syn / "retention.json").read_text())["videos"]
    tables, embs = [], {}
    for vid in manifest.video_id:
        v = json.loads((raw / "videos" / f"{vid}.json").read_text())
        vf = build_video_features(vid, v["title"], v["description"], v["duration"], v["segments"], EMB, seg)
        R = ret[vid]["values"]
        t = vf.table
        t["retention_target"] = [retention_at(R, s) for s in t.start_time]
        t["drop_target"] = [retention_at(R, s) - retention_at(R, e) for s, e in zip(t.start_time, t.end_time)]
        t.loc[t.index[0], "retention_target"] = 100.0
        tables.append(t)
        embs[vid] = vf.embeddings
    df = pd.concat(tables, ignore_index=True)
    # families-per-archetype < 3 cannot be split 4/1/1, so use a simple video-level split for the tiny set
    vids = manifest.video_id.tolist()
    assign = {v: ("test" if i % 6 == 0 else "val" if i % 6 == 1 else "train") for i, v in enumerate(vids)}
    return df, embs, manifest, assign


def raw_video(root: Path, video_id: str) -> dict:
    return json.loads((root / "raw" / "synthetic_test" / "videos" / f"{video_id}.json").read_text())
