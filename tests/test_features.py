import numpy as np
import pytest

from src.embeddings import CachedEmbedder, HashingEmbedder
from src.features import schema
from src.features.emotion import emotion_features, lexicon_emotions
from src.features.engagement import engagement_features
from src.features.linguistic import linguistic_features
from src.features.pipeline import build_video_features
from src.features.similarity import similarity_context
from src.features.title import title_features


def segs(texts, seg=15):
    return [dict(segment_id=i, start_time=i * seg, end_time=(i + 1) * seg, text=t) for i, t in enumerate(texts)]


TEXTS = ["Hey guys welcome back to the channel today we are beating the final boss.",
         "The trick against the boss is to use your dodge roll before it charges, then punish with the sword.",
         "Yes! We did it! No way, the boss is finally down, let's go!",
         "The boss always charges first so timing your dodge roll is the key and the sword finishes it.",
         "Subscribe and smash the like button if you enjoyed this video."]


def test_linguistic_features_values():
    f = linguistic_features("I never give up. I never give in!", 10.0)
    assert f["word_count"] == 8 and f["sentence_count"] == 2 and f["vocabulary_size"] == 5
    assert f["words_per_second"] == pytest.approx(0.8) and f["speaking_rate"] == pytest.approx(48.0)
    assert f["unique_word_ratio"] == pytest.approx(5 / 8) and f["average_sentence_length"] == 4.0
    z = linguistic_features("", 15.0)
    assert z["word_count"] == 0 and z["unique_word_ratio"] == 0 and z["average_word_length"] == 0


def test_engagement_features():
    f = engagement_features("Hey guys, what do you think? Subscribe now! Let's go!")
    assert f["question_count"] == 1 and f["exclamation_count"] == 2 and f["cta_indicator"] == 1
    assert f["direct_audience_address"] >= 2 and f["imperative_sentence_count"] >= 2
    assert engagement_features("")["question_count"] == 0


def test_emotion_features_for_gaming_language():
    win = lexicon_emotions("Yes! Let's go, we did it, that was insane!")
    assert win["excitement"] > 0.5
    scary = lexicon_emotions("My health is almost gone and one wrong move means I die, so tense, I am scared")
    assert scary["fear"] > 0.3
    fail = lexicon_emotions("I died again, that is so unfair and frustrating")
    assert fail["anger"] > 0 and fail["sadness"] > 0
    calm = emotion_features("The map has three zones and a river in the middle")
    assert calm["emotional_intensity"] < 0.2
    assert 0 <= emotion_features("Wow, amazing, love it!!!")["emotional_intensity"] <= 1


def test_similarity_context_ignores_empty_and_handles_first():
    e = HashingEmbedder(64).encode(["alpha beta gamma", "alpha beta gamma", "", "delta epsilon"])
    empty = np.array([False, False, True, False])
    s = similarity_context(e, empty)
    assert s["sim_prev"][0] == 0 and s["sim_prev"][1] > 0.99 and s["sim_prev"][2] == 0 and s["sim_prev"][3] == 0  # prev is empty
    assert s["sim_any_earlier_max"][1] > 0.99


def test_pipeline_schema_and_no_nans():
    emb = HashingEmbedder(128)
    vf = build_video_features("v1", "Beating the final boss without dying", "desc", 75, segs(TEXTS), emb, 15)
    t = vf.table
    assert len(t) == 5 and vf.schema_version == schema.FEATURE_SCHEMA_VERSION == "1.0"
    for c in schema.PRE_PUBLICATION_FEATURES:
        assert c in t.columns
    assert not np.isnan(t[schema.PRE_PUBLICATION_FEATURES].to_numpy(float)).any()
    assert t["relative_position"].tolist() == pytest.approx([0, .2, .4, .6, .8])
    assert t["absolute_time"].tolist() == [0, 15, 30, 45, 60]
    assert not set(t.columns) & set(schema.POST_PUBLICATION_FEATURES)  # leakage guard on the produced table
    assert vf.embeddings.shape == (5, 128)


def test_repetition_features_detect_restated_ideas():
    emb = HashingEmbedder(256)
    vf = build_video_features("v1", "Boss fight guide", "", 75, segs(TEXTS), emb, 15)
    t = vf.table
    # segment 3 restates segment 1 in different words -> redundancy should exceed that of the unrelated CTA segment 4
    assert t["similarity_with_earlier_segments"].iloc[3] > t["similarity_with_earlier_segments"].iloc[4]
    assert t["semantic_novelty"].iloc[0] == 1.0 and t["semantic_novelty"].iloc[3] < t["semantic_novelty"].iloc[1]
    assert 0 <= t["information_density"].min() and t["information_density"].max() <= 1


def test_empty_segments_are_handled():
    emb = HashingEmbedder(64)
    texts = ["opening words here", "", "", "closing words here"]
    t = build_video_features("v", "title", "", 60, segs(texts), emb, 15).table
    assert t["word_count"].tolist()[1:3] == [0, 0] and t["information_density"].iloc[1] == 0
    assert not np.isnan(t[schema.PRE_PUBLICATION_FEATURES].to_numpy(float)).any()


def test_promise_gap_and_hook_numbers_are_derived():
    emb = HashingEmbedder(256)
    texts = ["hey guys welcome back subscribe to the channel", "quick update about the channel this month",
             "today the final boss battle begins in the castle", "the final boss battle continues"]
    t = build_video_features("v", "The final boss battle", "", 60, segs(texts), emb, 15).table
    assert t["promise_gap_seconds"].iloc[0] <= 45 and t["time_to_main_topic"].iloc[0] == t["promise_gap_seconds"].iloc[0]
    assert t["intro_length"].iloc[0] >= 15  # greeting-only opening
    assert 0 <= t["hook_strength"].iloc[0] <= 1


def test_title_alignment_unit():
    te = np.array([1.0, 0.0])
    emb = np.array([[0.0, 1.0], [0.9, 0.1], [1.0, 0.0]])
    out = title_features(te, emb / np.linalg.norm(emb, axis=1, keepdims=True), [0, 15, 30], np.zeros(3, bool), 45)
    assert out[0]["promise_gap_seconds"] == 15 and out[2]["is_after_promise"] == 1 and out[0]["is_after_promise"] == 0


def test_embedding_cache_avoids_recomputation(tmp_path):
    calls = []

    class Counting(HashingEmbedder):
        def encode(self, texts):
            calls.append(len(texts))
            return super().encode(texts)

    c = CachedEmbedder(Counting(32), cache_dir=tmp_path)
    a = c.encode(["x y", "z w", "x y"])
    c.save()
    c2 = CachedEmbedder(Counting(32), cache_dir=tmp_path)
    b = c2.encode(["z w", "x y"])
    assert calls == [2] and np.allclose(a[1], b[0]) and np.allclose(a[0], b[1])  # second instance served from disk, nothing recomputed
