"""Dataset statistics / sanity checks for the synthetic corpus (used in docs and tests)."""
import json
from collections import Counter

import numpy as np
import pandas as pd

from src import config


def load_manifest(version: str = config.DATASET_VERSION) -> pd.DataFrame:
    return pd.read_csv(config.synthetic_dir(version) / "manifest.csv")


def load_retention(version: str = config.DATASET_VERSION) -> dict:
    return json.loads((config.synthetic_dir(version) / "retention.json").read_text(encoding="utf-8"))["videos"]


def load_raw_video(video_id: str, version: str = config.DATASET_VERSION) -> dict:
    return json.loads((config.raw_dir(version) / "videos" / f"{video_id}.json").read_text(encoding="utf-8"))


def dataset_stats(version: str = config.DATASET_VERSION) -> dict:
    man = load_manifest(version)
    ret = load_retention(version)
    texts, rises, early30, late, ends, mono = [], [], [], [], [], 0
    for vid, r in ret.items():
        v = np.array(r["values"])
        ends.append(v[-1])
        early30.append(100 - v[min(30, len(v) - 1)])
        d = np.diff(v)
        rises.append(float((d > 0.05).mean()))
        mono += int((d <= 1e-9).all())
    for vid in man.video_id[:60]:
        texts += [s["text"] for s in load_raw_video(vid, version)["segments"]]
    all_texts = []
    for vid in man.video_id:
        all_texts += [s["text"] for s in load_raw_video(vid, version)["segments"]]
    c = Counter(all_texts)
    words = [len(t.split()) for t in all_texts]
    return dict(
        n_videos=int(len(man)), n_archetypes=int(man.archetype.nunique()), n_families=int(man.template_family_id.nunique()),
        duration_min=float(man.duration.min()), duration_max=float(man.duration.max()), duration_mean=float(man.duration.mean()),
        n_cues_total=int(man.n_cues.sum()), unique_cue_text_ratio=len(c) / len(all_texts), mean_words_per_cue=float(np.mean(words)),
        end_retention_mean=float(np.mean(ends)), end_retention_min=float(np.min(ends)), end_retention_max=float(np.max(ends)),
        early_30s_loss_mean=float(np.mean(early30)), fraction_of_seconds_with_increase=float(np.mean(rises)),
        strictly_monotone_videos=int(mono),
        end_retention_by_archetype={k: round(float(v), 1) for k, v in man.groupby("archetype").end_retention.mean().items()},
    )


if __name__ == "__main__":
    print(json.dumps(dataset_stats(), indent=2))
