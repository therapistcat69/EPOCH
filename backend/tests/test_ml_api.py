"""ML integration tests. The model itself is replaced by a fake PredictionService so these tests are fast and need no
torch / embedding model; the real model is exercised in the repo-root tests (tests/test_inference.py)."""
import json

import httpx
import pytest
import respx

from app.errors import AppError
from app.services import ml_bridge, ml_explain_service
from app.services.groq_service import GroqService
from app.services.ml_service import get_prediction_service
from tests.creator_fixtures import ANALYTICS  # noqa: F401
from tests.fixtures import VIDEO_ID
from tests.test_creator_flow import mock_creator_apis
from tests.test_oauth import do_login
from tests.test_transcripts_and_analysis import SRT

GROQ = "https://api.groq.com/openai/v1"


def fake_prediction(video_id="v", duration=75.0, trained_on="synthetic"):
    pts = [dict(start_seconds=i * 15.0, end_seconds=(i + 1) * 15.0, time_ratio=i * 15.0 / duration, predicted_retention=100 - 8 * i) for i in range(5)]
    return dict(
        video_id=video_id, model_name="xgb", model_version="v1", feature_schema_version="1.0", dataset_version="synthetic_v1", trained_on=trained_on,
        data_mode_warning="DEVELOPMENT / SYNTHETIC DATA: synthetic", segment_seconds=15.0, duration_seconds=duration, embedding_model="all-MiniLM-L6-v2",
        points=pts, normalized_curve=[dict(time_ratio=i / 100, predicted_retention=100 - 0.4 * i) for i in range(101)],
        risk_segments=[dict(start_seconds=30.0, end_seconds=45.0, risk_score=0.72, predicted_drop=9.5, contributing_features=["redundant_information_score"],
                            factors=[dict(feature="redundant_information_score", group="repetition", contribution=2.1, direction="high",
                                          label="high redundancy with earlier content")],
                            explanation="Compared with the rest of this video...", explanation_type="MODEL-BASED EXPLANATION")],
        uncertainty=dict(available=False, method=None, std=[], lower=[], upper=[], note="uncertainty estimate unavailable"), warnings=[],
    )


class FakeService:
    def __init__(self):
        self.calls = []

    async def predict(self, request):
        self.calls.append(request)
        if not (request.transcript or {}).get("segments"):
            raise AppError("TRANSCRIPT_REQUIRED", "A transcript with timestamped segments is required.", 422)
        return fake_prediction(request.video_id, float((request.video or {}).get("duration_seconds") or 75))


@pytest.fixture
def fake(app):
    svc = FakeService()
    app.dependency_overrides[get_prediction_service] = lambda: svc
    return svc


def test_status_shape_and_synthetic_distinction():
    s = ml_bridge.status()
    for k in ("model_available", "state", "model_name", "model_version", "feature_schema_version", "trained_on", "real_validation_available", "message"):
        assert k in s
    assert s["real_validation_available"] is False  # mandatory: never claim real validation for a synthetic-trained model


async def test_predict_contract_with_fake_model(api, fake):
    body = {"video_id": "v1", "video": {"title": "T", "duration_seconds": 75}, "transcript": {"segments": [{"segment_id": 0, "start": 0, "end": 15, "text": "hi"}]}}
    r = await api.post("/api/ml/predict", json=body)
    assert r.status_code == 200
    p = r.json()
    assert p["trained_on"] == "synthetic" and "SYNTHETIC" in p["data_mode_warning"]
    assert len(p["points"]) == 5 and p["points"][0]["predicted_retention"] == 100 and len(p["normalized_curve"]) == 101
    assert p["risk_segments"][0]["explanation_type"] == "MODEL-BASED EXPLANATION" and 0 <= p["risk_segments"][0]["risk_score"] <= 1
    assert p["uncertainty"]["available"] is False
    assert fake.calls[0].video["title"] == "T"


async def test_predict_requires_transcript_and_video_id(api, fake):
    r = await api.post("/api/ml/predict", json={"video_id": "v", "video": {}, "transcript": {}})
    assert r.status_code == 422 and r.json()["error"]["code"] == "TRANSCRIPT_REQUIRED"
    assert (await api.post("/api/ml/predict", json={"video": {}})).status_code == 422


async def test_demo_videos_are_held_out_and_labelled(api):
    r = (await api.get("/api/ml/demo/videos")).json()
    assert r["label"] == "DEVELOPMENT / SYNTHETIC DATA" and r["data_mode"] == "synthetic"
    if not r["videos"]:
        pytest.skip("synthetic dataset not present")
    assert len(r["videos"]) <= 70 and all(v["split"] == "test" for v in r["videos"])


async def test_demo_prediction_shows_synthetic_target_never_actual(api, fake):
    vids = (await api.get("/api/ml/demo/videos")).json()["videos"]
    if not vids:
        pytest.skip("synthetic dataset not present")
    d = (await api.get(f"/api/ml/demo/{vids[0]['video_id']}")).json()
    assert d["data_mode"] == "synthetic" and d["label"] == "DEVELOPMENT / SYNTHETIC DATA"
    assert len(d["synthetic_target"]) == 101 and d["synthetic_target"][0]["retention"] == pytest.approx(100, abs=2)
    assert "actual" not in d and "Synthetic target" in d["disclaimer"]
    assert d["prediction"]["trained_on"] == "synthetic" and d["transcript"]["segments"]


async def test_demo_rejects_training_videos(api, fake):
    vids = {v["video_id"] for v in (await api.get("/api/ml/demo/videos")).json()["videos"]}
    if not vids:
        pytest.skip("synthetic dataset not present")
    train_id = next(f"video_{i:04d}" for i in range(1, 421) if f"video_{i:04d}" not in vids)
    r = await api.get(f"/api/ml/demo/{train_id}")
    assert r.status_code == 404 and r.json()["error"]["code"] == "DEMO_VIDEO_NOT_FOUND"


@respx.mock
async def test_creator_prediction_separates_actual_from_predicted(api, fake):
    mock_creator_apis()
    await do_login(api)
    await api.post("/api/sync")
    none = (await api.get(f"/api/video/{VIDEO_ID}/prediction")).json()
    assert none["available"] is False and none["reason"] == "NO_TRANSCRIPT"  # graceful, no failure
    await api.post(f"/api/video/{VIDEO_ID}/transcript/upload", json={"format": "srt", "content": SRT, "language": "en"})
    r = (await api.get(f"/api/video/{VIDEO_ID}/prediction")).json()
    assert r["available"] and r["prediction"]["trained_on"] == "synthetic"
    assert r["actual"]["available"] is True and len(r["actual"]["points"]) == 3  # YouTube Analytics retention, kept separate
    assert fake.calls[-1].transcript["segments"][0]["text"].startswith("Today we are comparing")


# ---------------------------------------------------------------------------- Groq explanation guard rails
def groq_explanation(entries):
    return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({"summary": "The model flags one region.", "risk_explanations": entries})}}]})


@respx.mock
async def test_groq_explains_but_cannot_invent_regions():
    pred = fake_prediction()
    segs = [{"start": 30, "end": 45, "text": "I said it again, the same thing"}]
    route = respx.post(f"{GROQ}/chat/completions").mock(return_value=groq_explanation([
        {"start_seconds": 30.0, "end_seconds": 45.0, "what_is_happening": "Repeats earlier wording.", "possible_experiment": "Consider testing a shorter version."},
        {"start_seconds": 99.0, "end_seconds": 120.0, "what_is_happening": "INVENTED", "possible_experiment": "x"},
    ]))
    out = await ml_explain_service.explain(GroqService(), pred, segs, "T")
    assert out["available"]
    kept = out["report"]["risk_explanations"]
    assert len(kept) == 1 and kept[0]["start_seconds"] == 30.0  # the invented region is dropped
    sent = json.loads(route.calls[0].request.content)["messages"]
    text = " ".join(m["content"] for m in sent)
    assert "never alter" in text.lower() and "risk_score" in text and "not validated on real YouTube retention" in text  # numbers come from the model
    assert "redundancy" in text  # model-attributed features are supplied as evidence


async def test_groq_explanation_degrades_gracefully(monkeypatch):
    out = await ml_explain_service.explain(GroqService(api_key=""), fake_prediction(), [], "T")
    assert out == {"available": False, "reason": "GROQ_NOT_CONFIGURED", "message": "AI explanation unavailable: GROQ_API_KEY is not set on the server."}
    p = fake_prediction()
    p["risk_segments"] = []
    out = await ml_explain_service.explain(GroqService(), p, [], "T")
    assert out["available"] is False and out["reason"] == "NO_RISK_REGIONS"


@respx.mock
async def test_groq_failure_does_not_break_prediction_explanation():
    respx.post(f"{GROQ}/chat/completions").mock(return_value=httpx.Response(429, json={}))
    out = await ml_explain_service.explain(GroqService(), fake_prediction(), [], "T")
    assert out["available"] is False and out["reason"] == "GROQ_RATE_LIMITED"
