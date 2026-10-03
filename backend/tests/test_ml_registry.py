"""Model registry, promotion rule, admin gating, retraining workflow, feedback loop and pasted-transcript prediction."""
import json
from pathlib import Path

import pytest

from app.services import ml_registry
from app.services.ml_service import get_prediction_service
from tests.test_ml_api import FakeService


def meta(version, mae, pearson=0.89, recall=0.63):
    return dict(model_name="xgb_delta", model_version=version, dataset_version="synthetic_v1", feature_schema_version="1.0", trained_on="synthetic",
                training_samples=280, synthetic_samples=350, real_samples=0,
                test_metrics=dict(regression=dict(mae=mae, rmse=6.0, r2=0.79, pearson=pearson, spearman=0.87), risk=dict(risk_recall=recall)))


def test_promotion_rule_blocks_worse_candidates():
    prod = meta("v1", 4.8)
    assert ml_registry.decide(meta("v2", 4.7), prod)[0] is True
    ok, msg = ml_registry.decide(meta("v2", 5.2), prod)
    assert ok is False and "mae_not_worse=FAIL" in msg
    assert ml_registry.decide(meta("v2", 4.7, pearson=0.85), prod)[0] is False
    assert ml_registry.decide(meta("v2", 4.7, recall=0.40), prod)[0] is False


def test_curve_error_is_zero_for_identical_curves():
    pred = [dict(time_ratio=i / 10, predicted_retention=100 - 5 * i) for i in range(11)]
    act = [dict(time_ratio=i / 10, value=100 - 5 * i) for i in range(11)]
    e = ml_registry.curve_error(pred, act)
    assert e["mae"] == pytest.approx(0, abs=1e-9) and e["pearson"] == pytest.approx(1)


async def seed(session_factory, tmp_path):
    out = {}
    async with session_factory() as s:
        for v, st in (("v1", "production"), ("v2", "archived")):
            d = tmp_path / v
            d.mkdir()
            (d / "metadata.json").write_text(json.dumps(meta(v, 4.8)))
            s.add(ml_registry._row_from_meta(meta(v, 4.8), d, st))
            out[v] = d
        await s.commit()
    return out


async def test_only_one_production_and_rollback(api, session_factory, tmp_path, monkeypatch):
    await seed(session_factory, tmp_path)
    monkeypatch.setattr(ml_registry.ml_bridge, "set_model_dir", lambda p: None)
    r = await api.post("/api/ml/models/v2/promote")
    assert r.status_code == 200 and r.json()["status"] == "production"
    models = (await api.get("/api/ml/models")).json()["models"]
    assert [m["model_version"] for m in models if m["status"] == "production"] == ["v2"]
    await api.post("/api/ml/models/v1/promote")  # rollback
    models = (await api.get("/api/ml/models")).json()["models"]
    assert [m["model_version"] for m in models if m["status"] == "production"] == ["v1"]
    assert (await api.post("/api/ml/models/v9/promote")).status_code == 404


async def test_rejected_model_cannot_be_promoted(api, session_factory, tmp_path, monkeypatch):
    d = await seed(session_factory, tmp_path)
    monkeypatch.setattr(ml_registry.ml_bridge, "set_model_dir", lambda p: None)
    async with session_factory() as s:
        s.add(ml_registry._row_from_meta(meta("v3", 9.0), d["v1"], "rejected"))
        await s.commit()
    r = await api.post("/api/ml/models/v3/promote")
    assert r.status_code == 409 and r.json()["error"]["code"] == "MODEL_REJECTED"


async def test_admin_token_gates_retraining(api, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "s3cret")
    from app.config import get_settings

    get_settings.cache_clear()
    try:
        assert (await api.post("/api/ml/retrain", json={})).status_code == 403
        assert (await api.post("/api/ml/models/v1/promote", headers={"x-admin-token": "wrong"})).status_code == 403
    finally:
        get_settings.cache_clear()


async def test_retrain_requires_enough_labels_for_label_trigger(api, session_factory, tmp_path, monkeypatch):
    await seed(session_factory, tmp_path)
    monkeypatch.setattr(ml_registry.ml_bridge, "artifact_meta", lambda: meta("v1", 4.8))
    r = await api.post("/api/ml/retrain", json={"reason": "new_labels", "force": False})
    assert r.status_code == 409 and r.json()["error"]["code"] == "INSUFFICIENT_TRAINING_DATA"


async def test_retrain_run_rejects_worse_candidate_and_keeps_production(api, session_factory, tmp_path, monkeypatch):
    await seed(session_factory, tmp_path)
    monkeypatch.setattr(ml_registry.ml_bridge, "artifact_meta", lambda: meta("v1", 4.8))
    monkeypatch.setattr(ml_registry.ml_bridge, "set_model_dir", lambda p: None)
    monkeypatch.setattr(ml_registry, "CANDIDATES_DIR", tmp_path / "cand")

    class Proc:
        returncode = 0
        stderr = b""

    def fake_run(*a, **k):
        out = ml_registry.CANDIDATES_DIR / "v3"
        out.mkdir(parents=True)
        (out / "metadata.json").write_text(json.dumps(meta("v3", 6.0)))  # clearly worse
        return Proc()

    monkeypatch.setattr(ml_registry.subprocess, "run", fake_run)
    r = await api.post("/api/ml/retrain", json={"reason": "manual"})
    assert r.status_code == 200 and r.json()["candidate_version"] == "v3"
    import asyncio

    for _ in range(50):
        if ml_registry._running["run_id"] is None:
            break
        await asyncio.sleep(0.05)
    d = (await api.get("/api/ml/models")).json()
    status = {m["model_version"]: m["status"] for m in d["models"]}
    assert status["v3"] == "rejected" and status["v1"] == "production"
    assert d["training_runs"][0]["decision"].startswith("REJECTED")


async def test_metrics_do_not_warn_about_drift_on_tiny_samples(api, session_factory, tmp_path):
    await seed(session_factory, tmp_path)
    m = (await api.get("/api/ml/metrics")).json()
    assert m["drift_warning"] is None and "Not enough real labelled videos" in m["drift_note"]
    assert m["real_labeled_videos"] == 0 and m["prediction_count"] == 0


async def test_predict_text_works_on_arbitrary_pasted_transcript(app, api):
    svc = FakeService()
    app.dependency_overrides[get_prediction_service] = lambda: svc
    srt = "1\n00:00:00,000 --> 00:00:15,000\nToday we try something new.\n\n2\n00:00:15,000 --> 00:00:30,000\nHere is the boss fight!\n"
    r = await api.post("/api/ml/predict-text", json={"title": "My video", "format": "srt", "content": srt})
    assert r.status_code == 200
    assert svc.calls[0].transcript["segments"][1]["text"].startswith("Here is the boss")
    assert (await api.post("/api/ml/predict-text", json={"format": "srt", "content": "   "})).status_code == 422
