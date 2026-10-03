"""Smoke test of the feature pipeline on one synthetic video (python -m src.features.smoke [embedder])."""
import sys
import time

import numpy as np

from src import config
from src.data_generation.stats import load_raw_video
from src.embeddings import get_embedder
from src.features import schema
from src.features.pipeline import build_video_features

name = sys.argv[1] if len(sys.argv) > 1 else "hashing"
emb = get_embedder(name, cached=False)
v = load_raw_video("video_0005")
t0 = time.time()
vf = build_video_features(v["video_id"], v["title"], v["description"], v["duration"], v["segments"], emb, 15)
print(f"embedder={emb.name} segments={len(vf.table)} columns={vf.table.shape[1]} time={time.time() - t0:.2f}s")
num = vf.table[schema.PRE_PUBLICATION_FEATURES].to_numpy(float)
print("NaNs:", int(np.isnan(num).sum()), "| inf:", int(np.isinf(num).sum()), "| schema", schema.FEATURE_SCHEMA_VERSION)
cols = ["start_time", "word_count", "speaking_rate", "semantic_novelty", "redundant_information_score", "topic_change_score",
        "information_density", "emotional_intensity", "title_similarity"]
print(vf.table[cols].head(6).round(2).to_string())
print("video-level:", {c: round(float(vf.table[c].iloc[0]), 2) for c in ("intro_length", "time_to_first_action", "time_to_first_payoff", "time_to_main_topic", "hook_strength", "promise_gap_seconds")})
