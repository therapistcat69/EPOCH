import json

import numpy as np
import pytest

from src.data_generation.archetypes import ARCHETYPES
from src.data_generation.generate import generate_dataset
from src.data_generation.retention_sim import simulate_retention
from src.data_generation.transcript_gen import generate_video


@pytest.fixture(scope="module")
def small(tmp_path_factory):
    root = tmp_path_factory.mktemp("synth")
    info = generate_dataset(seed=7, families=2, per_family=2, version="synthetic_test", out_root=root)
    return root, info


def test_dataset_files_and_counts(small):
    root, info = small
    assert info["n_videos"] == len(ARCHETYPES) * 2 * 2
    raw = list((root / "raw" / "synthetic_test" / "videos").glob("*.json"))
    assert len(raw) == info["n_videos"]
    v = json.loads(raw[0].read_text())
    assert v["data_mode"] == "synthetic" and v["genre"] == "Gaming"
    assert {"video_id", "title", "duration", "genre", "subgenre", "segments"} <= set(v)
    assert {"segment_id", "start_time", "end_time", "text"} == set(v["segments"][0])  # no latent labels leak into the raw transcript


def test_video_durations_are_10_to_15_minutes(small):
    root, _ = small
    for p in (root / "raw" / "synthetic_test" / "videos").glob("*.json"):
        assert 590 <= json.loads(p.read_text())["duration"] <= 920


def test_generation_is_reproducible(tmp_path):
    a = generate_dataset(seed=3, families=1, per_family=1, version="r", out_root=tmp_path / "a")
    b = generate_dataset(seed=3, families=1, per_family=1, version="r", out_root=tmp_path / "b")
    fa = (tmp_path / "a" / "raw" / "r" / "videos" / "video_0001.json").read_text()
    fb = (tmp_path / "b" / "raw" / "r" / "videos" / "video_0001.json").read_text()
    ra = (tmp_path / "a" / "synthetic" / "r" / "retention.json").read_text()
    rb = (tmp_path / "b" / "synthetic" / "r" / "retention.json").read_text()
    assert fa == fb and ra == rb and a["n_videos"] == b["n_videos"]
    c = generate_dataset(seed=4, families=1, per_family=1, version="r", out_root=tmp_path / "c")
    assert (tmp_path / "c" / "raw" / "r" / "videos" / "video_0001.json").read_text() != fa  # a different seed changes the data


def test_transcripts_are_not_copies_of_each_other():
    texts = []
    for name in ("fast_challenge", "tutorial_guide", "review_style"):
        _, cues, _, _ = generate_video("v", name, 0, np.random.default_rng(1), 1)
        texts.append(" ".join(c["text"] for c in cues))
    assert len(set(texts)) == 3
    sets = [set(t.split()) for t in texts]
    assert len(sets[0] & sets[1]) / len(sets[0] | sets[1]) < 0.9


def test_cues_are_contiguous_and_text_matches_event_labels():
    _, cues, lat, _ = generate_video("v", "boss_fight", 1, np.random.default_rng(5), 5)
    assert all(abs(a["end_time"] - b["start_time"]) < 1e-6 for a, b in zip(cues, cues[1:]))
    assert cues[0]["start_time"] == 0 and len(cues) == len(lat)
    sponsor_text = [c["text"] for c, l in zip(cues, lat) if l.event == "SPONSOR"]
    assert all(any(k in t.lower() for k in ("sponsor", "code", "support the channel", "possible", "check them out")) for t in sponsor_text)
    assert not any("Hey guys, welcome back" in c["text"] for c, l in zip(cues, lat) if l.event == "GAMEPLAY_ACTION")


def _sim(name, seed=0, **trait_over):
    meta, cues, lat, info = generate_video("v", name, 0, np.random.default_rng(seed), seed)
    traits = {**info["traits"], **trait_over}
    return simulate_retention(cues, lat, traits, traits["sponsor_intrusiveness"], np.random.default_rng(seed + 1)), cues


def test_retention_constraints_and_plausibility():
    for name in ARCHETYPES:
        R, cues = _sim(name, 11)
        assert R[0] == 100.0 and R.min() >= 0 and R.max() <= 100
        assert 5 < R[-1] < 95, name
        assert len(R) >= int(cues[-1]["end_time"])


def test_retention_is_not_forced_monotone_but_mostly_decreasing():
    rises = 0
    for seed in range(12):
        R, _ = _sim("fast_challenge", seed)
        d = np.diff(R)
        rises += int((d > 1e-6).sum())
        assert R[-1] < R[0]
    assert rises > 0  # small local increases (rewatch bumps / noise) are allowed


def test_documented_generator_assumptions_hold():
    """Stronger hook -> less early loss; delayed payoff / more repetition -> lower retention (generator assumptions)."""
    base = np.mean([_sim("gameplay_commentary", s, hook_strength=0.9, repetition=0.05, payoff_latency=20)[0][30] for s in range(10)])
    weak = np.mean([_sim("gameplay_commentary", s, hook_strength=0.1, repetition=0.05, payoff_latency=20)[0][30] for s in range(10)])
    assert base > weak
    late = np.mean([_sim("boss_fight", s, payoff_latency=190)[0][200] for s in range(10)])
    early = np.mean([_sim("boss_fight", s, payoff_latency=20)[0][200] for s in range(10)])
    assert early > late
