import numpy as np
import pandas as pd
import pytest

from src.evaluation import metrics as M
from src.features import schema
from src.models import baselines
from src.training.splits import assert_no_leakage, describe_splits, family_splits, group_kfold


@pytest.fixture
def manifest():
    rows = []
    i = 0
    for a in ["a1", "a2", "a3"]:
        for f in range(6):
            for k in range(7):
                i += 1
                rows.append(dict(video_id=f"v{i}", archetype=a, template_family_id=f"{a}:{f}"))
    return pd.DataFrame(rows)


def test_no_video_in_two_splits_and_families_are_held_out(manifest):
    assign = family_splits(manifest, 42)
    assert set(assign.values()) == {"train", "val", "test"}
    assert len(assign) == len(manifest)
    assert_no_leakage(manifest, assign)  # raises if a family or video straddles splits
    m = manifest.assign(split=manifest.video_id.map(assign))
    fam_split = m.groupby("template_family_id").split.nunique()
    assert (fam_split == 1).all()
    train_f, test_f = set(m[m.split == "train"].template_family_id), set(m[m.split == "test"].template_family_id)
    assert not train_f & test_f
    d = describe_splits(manifest, assign)
    assert d["train"]["videos"] > d["val"]["videos"] == d["test"]["videos"] and d["val"]["videos"] > 0


def test_leakage_detection_triggers(manifest):
    assign = family_splits(manifest, 1)
    bad = dict(assign)
    victim = manifest.iloc[0]
    bad[victim.video_id] = "test" if assign[victim.video_id] != "test" else "train"
    with pytest.raises(AssertionError):
        assert_no_leakage(manifest, bad)


def test_splits_are_reproducible_and_seed_dependent(manifest):
    assert family_splits(manifest, 5) == family_splits(manifest, 5)
    assert family_splits(manifest, 5) != family_splits(manifest, 6)


def test_group_kfold_never_splits_a_video():
    df = pd.DataFrame(dict(video_id=np.repeat([f"v{i}" for i in range(20)], 10), x=range(200)))
    for tr, te in group_kfold(df, 5):
        assert not set(df.video_id.iloc[tr]) & set(df.video_id.iloc[te])


def test_leakage_guard_rejects_post_publication_columns():
    schema.assert_pre_publication(schema.PRE_PUBLICATION_FEATURES)  # the real feature list is clean
    for col in ("views", "likes", "comments", "actual_retention", "subscribers_gained", "retention_target"):
        with pytest.raises(ValueError):
            schema.assert_pre_publication(["word_count", col])
    assert not set(schema.PRE_PUBLICATION_FEATURES) & set(schema.POST_PUBLICATION_FEATURES)


def test_regression_metrics_known_values():
    m = M.regression_metrics([1, 2, 3, 4], [1, 2, 3, 4])
    assert m["mae"] == 0 and m["rmse"] == 0 and m["r2"] == 1 and m["pearson"] == pytest.approx(1)
    m = M.regression_metrics([0, 10], [5, 5])
    assert m["mae"] == 5 and m["rmse"] == 5 and m["r2"] < 0.01


def test_curve_metrics():
    t = [np.array([100, 90, 80, 70.0])]
    c = M.curve_metrics(t, t, [np.full(4, 15.0)])
    assert c["avg_pointwise_error"] == 0 and c["curve_shape_corr"] == pytest.approx(1)
    c2 = M.curve_metrics(t, [np.array([100, 95, 85, 80.0])], [np.full(4, 15.0)])
    assert c2["max_error"] == 10 and c2["area_between_curves"] == pytest.approx((0 + 5 + 5 + 10) * 15)


def test_risk_threshold_uses_train_distribution_only():
    drops = np.array([-1, 0, 1, 2, 3, 4, 5, 6, 7, 8.0])
    tau = M.risk_threshold_from_train(drops, 0.8)
    assert tau == pytest.approx(np.quantile(drops[drops > 0], 0.8))
    labels = M.risk_labels(drops, tau)
    assert labels.sum() >= 1 and not labels[drops <= 0].any()


def test_risk_localisation_metrics():
    labels = [np.array([0, 0, 1, 0, 0, 1, 0], bool)]
    perfect = [np.array([0, 0, 9, 0, 0, 8, 0.0])]
    r = M.risk_metrics(perfect, labels, thr=5)
    assert r["top1_hit"] == 1 and r["top3_hit"] == 1 and r["risk_recall"] == 1 and r["risk_precision"] == 1 and r["risk_iou"] == 1
    miss = [np.array([9, 8, 0, 0, 0, 0, 7.0])]
    r = M.risk_metrics(miss, labels, thr=5)
    assert r["top1_hit"] == 0 and r["risk_recall"] == 0
    assert M.pred_risk_from_curve(np.array([100, 90, 95, 80.0])).tolist() == [10, 0, 15, 0]


def test_naive_baselines_work_and_stay_in_range():
    df = pd.DataFrame(dict(relative_position=np.linspace(0, 1, 50)))
    y = 100 - 50 * df.relative_position.to_numpy()
    for cls in baselines.BASELINES:
        p = cls().fit(df, y).predict(df)
        assert p.shape == (50,) and p.min() >= 0 and p.max() <= 100
    assert np.abs(baselines.LinearDecayBaseline().fit(df, y).predict(df) - y).max() < 1e-6
    assert np.abs(baselines.PolynomialBaseline().fit(df, y).predict(df) - y).max() < 1e-6
