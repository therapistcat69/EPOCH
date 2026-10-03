"""Print one synthetic video's transcript head, generator event labels and retention curve (for eyeballing the data)."""
import json
import sys

from src import config
from src.data_generation.stats import load_raw_video, load_retention

vid = sys.argv[1] if len(sys.argv) > 1 else "video_0005"
n = int(sys.argv[2]) if len(sys.argv) > 2 else 8
v = load_raw_video(vid)
r = load_retention()[vid]["values"]
events = {}
with open(config.synthetic_dir() / "generator_meta.jsonl", encoding="utf-8") as f:
    for line in f:
        row = json.loads(line)
        if row["video_id"] == vid:
            events = {c["segment_id"]: c["event"] for c in row["cues"]}
print(f"{vid}: {v['title']} | {v['duration']}s | {v['game']}")
for s in v["segments"][:n]:
    print(f"  {s['start_time']:6.1f}-{s['end_time']:6.1f} [{events.get(s['segment_id'], '?'):15}] {s['text'][:130]}")
print("  retention @ 0/15/30/60/120/300/600s/end:", [round(r[min(t, len(r) - 1)], 1) for t in (0, 15, 30, 60, 120, 300, 600)], round(r[-1], 1))
