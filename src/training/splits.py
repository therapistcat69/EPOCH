"""Video-level, template-family-level splits (no leakage).

NEVER split segments of one video across train/validation/test. For synthetic data the unit of separation is the
whole TEMPLATE FAMILY (archetype + fixed trait offsets): validation/test then contain unseen combinations of hook
strength, pacing, repetition, topic structure and payoff timing - testing generalisation rather than memorisation of
generator templates.  Per archetype: 4 families train, 1 validation, 1 test (-> ~67/17/17 %).
"""
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold

from src import config


def family_splits(manifest: pd.DataFrame, seed: int = config.SEED) -> dict[str, str]:
    rng = np.random.default_rng(seed)
    assign: dict[str, str] = {}
    fam_split: dict[str, str] = {}
    for arch, g in manifest.groupby("archetype"):
        fams = sorted(g.template_family_id.unique())
        rng.shuffle(fams)
        for i, f in enumerate(fams):
            fam_split[f] = "test" if i == 0 else "val" if i == 1 else "train"
    for vid, fam in zip(manifest.video_id, manifest.template_family_id):
        assign[vid] = fam_split[fam]
    return assign


def assert_no_leakage(manifest: pd.DataFrame, assign: dict[str, str]) -> None:
    m = manifest.assign(split=manifest.video_id.map(assign))
    fam_splits = m.groupby("template_family_id").split.nunique()
    if (fam_splits > 1).any():
        raise AssertionError(f"template families straddle splits: {fam_splits[fam_splits > 1].index.tolist()[:3]}")
    vid_splits = m.groupby("video_id").split.nunique()
    if (vid_splits > 1).any():
        raise AssertionError("a video appears in more than one split")


def split_frame(df: pd.DataFrame, assign: dict[str, str], split: str) -> pd.DataFrame:
    return df[df.video_id.map(assign) == split].reset_index(drop=True)


def group_kfold(df: pd.DataFrame, n_splits: int = 5):
    """GroupKFold with group = video_id (segments of a video always stay together)."""
    return GroupKFold(n_splits=n_splits).split(df, groups=df.video_id)


def describe_splits(manifest: pd.DataFrame, assign: dict[str, str]) -> dict:
    m = manifest.assign(split=manifest.video_id.map(assign))
    return {s: dict(videos=int((m.split == s).sum()), families=int(m[m.split == s].template_family_id.nunique())) for s in ("train", "val", "test")}
