import json

import numpy as np
import pytest

from src import config
from src.embeddings import HashingEmbedder
from src.explainability import attribution as A
from src.features import schema
from src.features.pipeline import build_video_features
from src.inference import curve as C
from src.inference import risk as R
from src.inference.schema import EditSuggestion, PredictionResult
from src.models.flat_models import FlatRetentionModel, stack_embeddings
from tests.helpers import EMB, raw_video, tiny_dataset


@pytest.fixture(scope="module")
def data(tmp_path_factory):
    root = tmp_path_factory.mktemp("tiny")
    df, embs, manifest, assign = tiny_dataset(root)
    tr = df[df.video_id.map(assign) == "train"].reset_index(drop=True)
    va = df[df.video_id.map(assign) == "val"].reset_index(drop=True)
    te = df[df.video_id.map(assign) == "test"].reset_index(drop=True)
    assert not set(tr.video_id) & set(te.video_id) and not set(tr.video_id) & set(va.video_id)  # no video in two splits
    return dict(root=root, df=df, embs=embs, tr=tr, va=va, te=te)


@pytest.fixture(scope="module")
def xgb(data):
    m = FlatRetentionModel("xgb", ("hand", "emb"), 1, dict(n_estimators=60, max_depth=3))
    m.fit(data["tr"], stack_embeddings(data["tr"], data["embs"]), data["va"], stack_embeddings(data["va"], data["embs"]))
    return m


def test_flat_models_train_and_respect_retention_range(data):
    for kind in ("rf", "xgb"):
        m = FlatRetentionModel(kind, ("hand",), 1, dict(n_estimators=30))
        m.fit(data["tr"], None, data["va"], None)
        p = m.predict(data["te"])
        assert p.shape == (len(data["te"]),) and p.min() >= 0 and p.max() <= 100  # retention constraint [0, 100]
    m = FlatRetentionModel("rf", ("hand", "tfidf"), 1, dict(n_estimators=20))
    m.fit(data["tr"], None)
    assert any(n.startswith("tfidf_") for n in m.feature_names())


def test_model_save_load_roundtrip_is_identical(data, xgb, tmp_path):
    xgb.save(tmp_path)
    m2 = FlatRetentionModel.load(tmp_path)
    e = stack_embeddings(data["te"], data["embs"])
    assert np.allclose(xgb.predict(data["te"], e), m2.predict(data["te"], e))


def test_models_never_see_post_publication_or_target_columns():
    for sets in (("hand",), ("hand", "emb"), ("hand", "tfidf"), ("hand", "emb", "ctx")):
        m = FlatRetentionModel("xgb", sets)
        assert not set(m.hand_cols) & set(schema.POST_PUBLICATION_FEATURES)
        assert "retention_target" not in m.hand_cols and "drop_target" not in m.hand_cols
        schema.assert_pre_publication(m.hand_cols)


def test_context_features_are_causal(data):
    d = data["df"][data["df"].video_id == data["df"].video_id.iloc[0]]
    full = d["cum_mean_redundancy"].to_numpy()
    expected = d["redundant_information_score"].expanding().mean().to_numpy()
    assert np.allclose(full, expected)  # cumulative mean uses only past/current segments


# ---------------------------------------------------------------------------- explainability
def test_shap_values_are_additive(data, xgb):
    emb = stack_embeddings(data["te"], data["embs"])
    vals, names = A.shap_values_tree(xgb, data["te"].iloc[:30], emb[:30])
    assert vals.shape == (30, len(names))
    import shap

    base = shap.TreeExplainer(xgb.model).expected_value
    base = float(np.ravel(base)[0])
    pred = xgb.predict(data["te"].iloc[:30], emb[:30])
    unclipped = xgb.model.predict(xgb._matrix(data["te"].iloc[:30], emb[:30]))
    assert np.allclose(vals.sum(1) + base, unclipped, atol=1e-2)
    assert pred.shape == (30,)


def test_risk_contributions_use_shap_difference_for_absolute_target():
    sv = np.array([[1.0, 0.0], [3.0, 0.0], [0.0, 2.0]])
    names = ["semantic_novelty", "redundant_information_score"]
    c, an = A.risk_contributions(sv, names, 0, "retention_target")
    assert c.tolist() == [1.0 - 3.0, 0.0]  # decline = R_0 - R_1 -> shap_0 - shap_1
    c, _ = A.risk_contributions(sv, names, 1, "drop_target")
    assert c.tolist() == [3.0, 0.0]  # delta models: the segment's own SHAP


def test_factor_labels_are_descriptive_not_causal():
    import pandas as pd

    row = pd.Series({"redundant_information_score": 0.9, "semantic_novelty": 0.1})
    med = pd.Series({"redundant_information_score": 0.3, "semantic_novelty": 0.6})
    f = A.factors_for_segment(np.array([2.0, 1.0]), ["redundant_information_score", "semantic_novelty"], row, med)
    assert f[0]["label"] == "high redundancy with earlier content" and f[1]["label"] == "low semantic novelty"
    txt = A.explanation_text(0, 15, f)
    assert "not a causal reason" in txt and "cause" not in txt.replace("not a causal reason", "")
    assert "No single feature" in A.explanation_text(0, 15, [])


def test_group_importance_runs(data, xgb):
    e = stack_embeddings(data["va"], data["embs"])
    out = A.permutation_group_importance(lambda d: xgb.predict(d, e), data["va"], data["va"].retention_target.to_numpy(),
                                         {"position": schema.POSITION_COLUMNS, "repetition": schema.REPETITION_COLUMNS}, n_repeats=2)
    assert set(out) == {"position", "repetition"}


# ---------------------------------------------------------------------------- risk + curve
def test_risk_regions_merge_contiguous_segments_and_rank():
    starts = np.arange(8) * 15.0
    ends = starts + 15
    drops = np.array([0, 5, 6, 0, 0, 9, 0, 0.0])
    regs = R.detect_regions(starts, ends, drops, threshold=4, tau=3.0, top_n=5)
    assert [(r["start"], r["end"]) for r in regs] == [(75.0, 90.0), (15.0, 45.0)]  # sorted by risk, contiguous run merged
    assert regs[0]["risk_score"] == 1.0 and regs[1]["risk_score"] == pytest.approx(1.0) and all(0 <= r["risk_score"] <= 1 for r in regs)
    assert R.detect_regions(starts, ends, drops, 4, 3.0, top_n=1)[0]["start"] == 75.0
    assert R.detect_regions(starts, ends, np.zeros(8), 1, 3.0) == []


def test_curve_conversion_roundtrip():
    starts = np.arange(0, 600, 15.0)
    ret = 100 - np.linspace(0, 50, len(starts))
    ratios, vals = C.segments_to_normalized(starts, ret, 600)
    assert len(ratios) == 101 and ratios[0] == 0 and ratios[-1] == 1 and vals[0] == 100
    back = C.normalized_to_segments(ratios, vals, starts, 600)
    assert np.allclose(back, ret, atol=0.3)


# ---------------------------------------------------------------------------- inference pipeline
@pytest.fixture(scope="module")
def artifact(data, xgb, tmp_path_factory):
    from src.evaluation import metrics as M

    d = tmp_path_factory.mktemp("artifact")
    xgb.save(d)
    tau = M.risk_threshold_from_train(data["tr"].drop_target.to_numpy())
    meta = dict(model_name="xgb_test", model_version="vtest", kind="flat", family="xgb", target="retention_target", dataset_version="synthetic_test",
                feature_schema_version=schema.FEATURE_SCHEMA_VERSION, trained_on="synthetic", segment_seconds=15, embedding_model="hashing-fallback",
                embedding_model_key="hashing", features="hand+emb", seed=1, risk_tau=tau, risk_threshold=tau * 0.5, uncertainty={})
    (d / "metadata.json").write_text(json.dumps(meta))
    return d


def test_inference_end_to_end_contract(data, artifact):
    from src.inference.pipeline import RetentionPredictor

    p = RetentionPredictor.load(artifact, embedder=HashingEmbedder(128))
    vid = data["te"].video_id.iloc[0]
    v = raw_video(data["root"], vid)
    res = p.predict(vid, v["title"], v["description"], v["duration"], v["segments"])
    PredictionResult.model_validate(res.model_dump())  # schema valid
    n = int(np.ceil(v["duration"] / 15))
    assert len(res.points) == n and res.points[0].start_seconds == 0 and res.points[0].time_ratio == 0
    assert all(0 <= x.predicted_retention <= 100 for x in res.points)
    assert len(res.normalized_curve) == 101 and res.normalized_curve[0].time_ratio == 0
    assert res.trained_on == "synthetic" and "SYNTHETIC" in res.data_mode_warning and res.uncertainty.available is False
    assert res.feature_schema_version == "1.0" and res.model_version == "vtest"
    for r in res.risk_segments:
        assert 0 <= r.risk_score <= 1 and r.start_seconds < r.end_seconds and r.explanation_type == "MODEL-BASED EXPLANATION"
        assert "not a causal reason" in r.explanation or "No single feature" in r.explanation


def test_inference_features_identical_to_training_features(data, artifact):
    """Training/inference parity: the same transcript must give byte-identical features through the shared pipeline."""
    vid = data["te"].video_id.iloc[1]
    v = raw_video(data["root"], vid)
    a = build_video_features(vid, v["title"], v["description"], v["duration"], v["segments"], EMB, 15).table
    b = build_video_features(vid, v["title"], v["description"], v["duration"], v["segments"], EMB, 15).table
    assert a[schema.PRE_PUBLICATION_FEATURES].equals(b[schema.PRE_PUBLICATION_FEATURES])
    trained = data["df"][data["df"].video_id == vid][schema.PRE_PUBLICATION_FEATURES].reset_index(drop=True)
    assert np.allclose(trained.to_numpy(float), a[schema.PRE_PUBLICATION_FEATURES].to_numpy(float))


def test_inference_handles_arbitrary_durations_and_messy_transcripts(data, artifact):
    from src.inference.pipeline import RetentionPredictor

    p = RetentionPredictor.load(artifact, embedder=HashingEmbedder(128))
    short = [dict(start=0, end=20, text="Today we test a thing."), dict(start=20, end=45, text="Here is the result of the thing.")]
    r = p.predict("s", "A test", "", 45, short)
    assert len(r.points) == 3
    long_ = [dict(start=i * 10, end=i * 10 + 10, text=f"segment number {i} talks about boss {i % 7} and item {i % 5}") for i in range(150)]
    r = p.predict("l", "Long video", "", 1500, long_)
    assert len(r.points) == 100 and r.points[-1].end_seconds == 1500  # not hard-coded to a number of segments
    messy = [dict(start="00:00:10,000", end="00:00:05,000", text="[Music] swapped times"), dict(start=0, end=10, text="hello hello"),
             dict(start=0, end=10, text="hello hello"), dict(start="garbage", end=3, text="dropped")]
    r = p.predict("m", "Messy", "", 30, messy)
    assert any("transcript cleaned" in w for w in r.warnings)
    with pytest.raises(ValueError):
        p.predict("e", "Empty", "", 30, [])


def test_inference_refuses_mismatched_embedding_or_schema(artifact, tmp_path):
    from src.inference.pipeline import RetentionPredictor

    with pytest.raises(ValueError, match="embedding model mismatch"):
        class Other(HashingEmbedder):
            name = "some-other-model"

        RetentionPredictor.load(artifact, embedder=Other(128))
    bad = tmp_path / "bad"
    bad.mkdir()
    meta = json.loads((artifact / "metadata.json").read_text())
    meta["feature_schema_version"] = "0.9"
    (bad / "metadata.json").write_text(json.dumps(meta))
    with pytest.raises(ValueError, match="feature schema"):
        RetentionPredictor.load(bad, embedder=HashingEmbedder(128))


def test_edit_suggestion_schema_has_no_predicted_effect():
    e = EditSuggestion(edit_type="cut", start=200, end=235, reason="repeated explanation", evidence=["similarity 0.9"])
    assert e.predicted_effect is None
    with pytest.raises(Exception):
        EditSuggestion(edit_type="cut", start=1, end=2, reason="x", predicted_effect=0.08)  # no fabricated expected improvement
