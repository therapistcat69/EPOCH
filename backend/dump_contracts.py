"""Regenerates the JSON Schemas in future-ml/contracts from the Pydantic models. Run from backend/:
    python dump_contracts.py
"""
import json
from pathlib import Path

from app.schemas.features import FeaturePayload
from app.schemas.ml import MLVideoFeatures, PredictRequest, PredictResponse

out = Path(__file__).resolve().parent.parent / "future-ml" / "contracts"
out.mkdir(parents=True, exist_ok=True)
for name, model in {
    "ml_video_features.schema.json": MLVideoFeatures,
    "feature_payload.schema.json": FeaturePayload,
    "predict_request.schema.json": PredictRequest,
    "predict_response.schema.json": PredictResponse,
}.items():
    (out / name).write_text(json.dumps(model.model_json_schema(), indent=2) + "\n", encoding="utf-8")
    print("wrote", name)
