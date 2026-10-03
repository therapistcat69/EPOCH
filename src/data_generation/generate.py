"""Generate the synthetic gaming dataset.

    python -m src.data_generation.generate --seed 42            # 420 videos -> data/raw + data/synthetic

Outputs (all tagged data_mode='synthetic'):
  data/raw/<version>/videos/<video_id>.json     video_id, title, description, duration, genre, subgenre, segments[cues]
  data/synthetic/<version>/retention.json       {video_id: {"fps": 1, "values": [...]}}      <- synthetic labels
  data/synthetic/<version>/generator_meta.jsonl latent traits + per-cue events (generator-internal, NEVER model input)
  data/synthetic/<version>/manifest.csv         one row per video incl. template_family_id and archetype
"""
import argparse
import csv
import json
from pathlib import Path

import numpy as np

from src import config
from src.data_generation.archetypes import ARCHETYPES, FAMILIES_PER_ARCHETYPE, VIDEOS_PER_FAMILY
from src.data_generation.retention_sim import simulate_retention
from src.data_generation.transcript_gen import generate_video


def generate_dataset(seed: int = config.SEED, families: int = FAMILIES_PER_ARCHETYPE, per_family: int = VIDEOS_PER_FAMILY,
                     version: str = config.DATASET_VERSION, out_root: Path | None = None) -> dict:
    raw = (out_root / "raw" / version) if out_root else config.raw_dir(version)
    syn = (out_root / "synthetic" / version) if out_root else config.synthetic_dir(version)
    (raw / "videos").mkdir(parents=True, exist_ok=True)
    syn.mkdir(parents=True, exist_ok=True)

    retention, meta_rows, manifest = {}, [], []
    i = 0
    for a_idx, name in enumerate(ARCHETYPES):
        for fam in range(families):
            for k in range(per_family):
                i += 1
                vid = f"video_{i:04d}"
                rng = np.random.default_rng([seed, a_idx, fam, k])
                meta, cues, latents, info = generate_video(vid, name, fam, rng, seed)
                traits = info["traits"]
                R = simulate_retention(cues, latents, traits, traits["sponsor_intrusiveness"], rng)
                video = dict(data_mode=config.MODE_SYNTHETIC, dataset_version=version, **meta, segments=cues_for_raw(cues))
                (raw / "videos" / f"{vid}.json").write_text(json.dumps(video), encoding="utf-8")
                retention[vid] = dict(fps=1, values=[round(float(x), 3) for x in R])
                meta_rows.append(dict(video_id=vid, **info, cues=[l.__dict__ for l in latents],
                                      note="generator-internal; never used as model input"))
                manifest.append(dict(video_id=vid, archetype=name, family_idx=fam, template_family_id=info["template_family_id"],
                                     duration=meta["duration"], title=meta["title"], n_cues=len(cues), end_retention=round(float(R[-1]), 2)))
    (syn / "retention.json").write_text(json.dumps(dict(data_mode=config.MODE_SYNTHETIC, dataset_version=version, videos=retention)), encoding="utf-8")
    with open(syn / "generator_meta.jsonl", "w", encoding="utf-8") as f:
        for row in meta_rows:
            f.write(json.dumps(row) + "\n")
    with open(syn / "manifest.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(manifest[0]))
        w.writeheader()
        w.writerows(manifest)
    return dict(n_videos=len(manifest), raw=str(raw), synthetic=str(syn), seed=seed)


def cues_for_raw(cues: list[dict]) -> list[dict]:
    """Raw transcript keeps only what a real caption file would have: id, start, end, text (no latent event labels)."""
    return [dict(segment_id=c["segment_id"], start_time=c["start_time"], end_time=c["end_time"], text=c["text"]) for c in cues]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=config.SEED)
    ap.add_argument("--families", type=int, default=FAMILIES_PER_ARCHETYPE)
    ap.add_argument("--per-family", type=int, default=VIDEOS_PER_FAMILY)
    a = ap.parse_args()
    print(generate_dataset(a.seed, a.families, a.per_family))
