"""ML endpoints. The prediction itself comes from the ML engine (models/retention_model_v1) via MLService."""
import hmac
from typing import Literal

from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.database import get_session
from app.deps import get_session_factory
from app.errors import AppError
from app.schemas.ml import MLPredictRequest
from app.services import ml_bridge, ml_explain_service, ml_registry
from app.services import transcript_service as ts
from app.services.groq_service import GroqService, get_groq_service
from app.services.ml_service import PredictionService, get_prediction_service

router = APIRouter(tags=["ml"])


@router.get("/api/ml/status")
async def ml_status():
    """Includes `trained_on` (synthetic/real) and `real_validation_available` - this distinction is mandatory."""
    return ml_bridge.status()


@router.post("/api/ml/predict")
async def predict(body: MLPredictRequest, service: PredictionService = Depends(get_prediction_service)):
    """Returns a PredictionResult. 501 when no trained model artifact is available."""
    return await service.predict(body)


@router.get("/api/ml/demo/videos")
async def demo_videos():
    """Held-out SYNTHETIC development videos (never used for training) for the demo view."""
    return {"data_mode": "synthetic", "label": "DEVELOPMENT / SYNTHETIC DATA", "videos": ml_bridge.demo_videos()}


@router.get("/api/ml/demo/{video_id}")
async def demo_prediction(
    video_id: str, explain: bool = False,
    service: PredictionService = Depends(get_prediction_service), groq: GroqService = Depends(get_groq_service),
):
    """Synthetic target vs model prediction for a held-out synthetic video. Always labelled DEVELOPMENT / SYNTHETIC DATA."""
    video = ml_bridge.demo_video(video_id)
    request = MLPredictRequest(video_id=video_id, video=dict(title=video["title"], description=video["description"], duration_seconds=video["duration_seconds"]),
                               transcript=video["transcript"])
    prediction = await service.predict(request)
    out = {**video, "prediction": prediction, "disclaimer": "Synthetic target vs model prediction. Development data only; not real YouTube audience behaviour."}
    if explain:
        out["groq"] = await ml_explain_service.explain(groq, prediction, video["transcript"]["segments"], video["title"])
    return out


# ----------------------------------------------------------------------------- transcript paste/upload -> prediction
class PredictTextRequest(BaseModel):
    title: str = ""
    description: str = ""
    duration_seconds: float | None = None
    format: Literal["txt", "srt", "vtt"] = "txt"
    content: str
    language: str | None = None


@router.post("/api/ml/predict-text")
async def predict_text(body: PredictTextRequest, service: PredictionService = Depends(get_prediction_service)):
    """Analyze ANY pasted/uploaded transcript (TXT/SRT/VTT): parse -> canonical schema -> the same inference pipeline."""
    t = ts.parse_upload(body.format, body.content, body.language, body.duration_seconds)
    segs = [dict(segment_id=s.segment_index, start=s.start_seconds, end=s.end_seconds, text=s.text) for s in t.segments]
    out = await service.predict(MLPredictRequest(
        video_id="adhoc", video=dict(title=body.title, description=body.description, duration_seconds=body.duration_seconds or t.duration_seconds),
        transcript=dict(segments=segs)))
    return {"prediction": out, "transcript": dict(segments=segs, timestamps_estimated=t.timestamps_estimated, language=t.language)}


# ----------------------------------------------------------------------------- model registry / retraining (admin only)
def require_admin(request: Request, x_admin_token: str | None = Header(default=None)) -> None:
    """Expensive/sensitive operations: ADMIN_TOKEN header when configured; otherwise loopback (local development) only."""
    token = get_settings().admin_token
    if token:
        if not hmac.compare_digest(x_admin_token or "", token):
            raise AppError("ADMIN_ONLY", "This operation is restricted to administrators.", 403)
    elif (request.client.host if request.client else "") not in ("127.0.0.1", "::1", "localhost", "testclient"):
        raise AppError("ADMIN_ONLY", "Set ADMIN_TOKEN to enable this operation outside local development.", 403)


class RetrainRequest(BaseModel):
    reason: Literal["manual", "scheduled", "new_labels"] = "manual"
    force: bool = False


@router.get("/api/ml/models")
async def models(session: AsyncSession = Depends(get_session)):
    """Registry: every model version with its status (candidate | production | rejected | archived) and recent training runs."""
    await ml_registry.ensure_production(session)
    return {"models": await ml_registry.list_models(session), "training_runs": await ml_registry.runs(session),
            "retrain_after_real_labels": get_settings().retrain_after_real_labels}


@router.post("/api/ml/retrain", dependencies=[Depends(require_admin)])
async def retrain(body: RetrainRequest, session: AsyncSession = Depends(get_session), factory=Depends(get_session_factory)):
    """Starts a candidate training run in the background; the candidate is promoted only if it passes the promotion rule."""
    await ml_registry.ensure_production(session)
    return await ml_registry.start_retrain(factory, body.reason, body.force)


@router.post("/api/ml/models/{version}/promote", dependencies=[Depends(require_admin)])
async def promote(version: str, session: AsyncSession = Depends(get_session)):
    """Manual promotion / rollback to an archived or candidate version."""
    return await ml_registry.promote(session, version)


@router.get("/api/ml/metrics")
async def ml_metrics(session: AsyncSession = Depends(get_session)):
    """Prediction count, real labelled videos, recent real-data error and a drift warning (only with enough real samples)."""
    await ml_registry.ensure_production(session)
    return await ml_registry.metrics(session)
