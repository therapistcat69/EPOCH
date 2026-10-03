"""Sanity check: do the embedding models see paraphrases as similar (semantic repetition) and unrelated text as different?"""
import sys
import time

import numpy as np

from src.embeddings import get_embedder

PAIRS = [
    ("AI is going to completely change development.", "Software development will be transformed by AI.", "paraphrase (spec example)"),
    ("The trick against the boss is to use your dodge roll before it charges.", "The boss always charges first, so timing your dodge roll is the key.", "paraphrase (gaming)"),
    ("The trick against the boss is to use your dodge roll before it charges.", "Make sure you subscribe and turn on notifications.", "unrelated"),
    ("Yes! We finally beat the final boss!", "Honestly the soundtrack in this game is beautiful.", "unrelated"),
]
for key in (sys.argv[1:] or ["minilm"]):
    t0 = time.time()
    e = get_embedder(key, cached=False)
    load = time.time() - t0
    v = e.encode([x for p in PAIRS for x in p[:2]])
    print(f"== {e.name} (dim {e.dim}, device {getattr(e.base if hasattr(e, 'base') else e, 'device', '-')}) load {load:.1f}s")
    for i, (a, b, label) in enumerate(PAIRS):
        print(f"   cos={float(v[2 * i] @ v[2 * i + 1]):.3f}  {label}")
    t0 = time.time()
    e.encode(["this is a sample sentence for timing purposes number %d" % i for i in range(512)])
    print(f"   throughput: {512 / (time.time() - t0):.0f} sentences/s")
