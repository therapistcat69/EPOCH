"""Build processed datasets (features + cached embeddings) for the configurations used in the experiments.

    python -m src.training.build_all                 # 15 s + MiniLM first, then other sizes / the multilingual model
    python -m src.training.build_all --only 15:minilm
"""
import argparse
import os
import time

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from src import config
from src.embeddings import get_embedder
from src.training.dataset import build_dataset

DEFAULT_CONFIGS = [(15, "minilm"), (10, "minilm"), (20, "minilm"), (30, "minilm"), (15, "multilingual")]

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", help="e.g. 15:minilm 30:minilm")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    cfgs = [(int(x.split(":")[0]), x.split(":")[1]) for x in a.only] if a.only else DEFAULT_CONFIGS
    embedders = {}
    for seg, name in cfgs:
        t0 = time.time()
        if name not in embedders:
            embedders[name] = get_embedder(name)
        ds = build_dataset(seg, embedders[name], force=a.force)
        print(f"[{time.time() - t0:6.1f}s] seg={seg}s embedder={name}: {len(ds['df'])} segments, {len(ds['curves'])} videos", flush=True)
    print("done", flush=True)
