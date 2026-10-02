"""THE ML PLUG-IN POINT.

To connect Random Forest / XGBoost later:
  1. Implement `PredictionService.predict` (load the trained model, build the feature vector
     from `FeaturePayload`, return a `PredictResponse`).
  2. Return your implementation from `get_prediction_service()` below.
  3. Persist results into the `future_predictions` table.
Nothing else in the backend needs to change. See docs/ml-integration.md.
"""
from typing import Protocol

from app.errors import AppError
from app.schemas.ml import PredictRequest, PredictResponse


class PredictionService(Protocol):
    async def predict(self, request: PredictRequest) -> PredictResponse: ...


class NotConnectedPredictionService:
    async def predict(self, request: PredictRequest) -> PredictResponse:
        raise AppError(
            "ML_NOT_IMPLEMENTED",
            "The ML prediction pipeline is not connected yet.",
            501,
        )


def get_prediction_service() -> PredictionService:
    return NotConnectedPredictionService()
