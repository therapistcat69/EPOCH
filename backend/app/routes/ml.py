from fastapi import APIRouter, Depends

from app.schemas.ml import PredictRequest, PredictResponse
from app.services.ml_service import PredictionService, get_prediction_service

router = APIRouter()


@router.post("/api/ml/predict", response_model=PredictResponse)
async def predict(body: PredictRequest, service: PredictionService = Depends(get_prediction_service)):
    """Contract only. Returns 501 until a PredictionService is connected."""
    return await service.predict(body)
