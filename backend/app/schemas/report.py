import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.features import FeaturePayload, FeatureStatus
from app.schemas.youtube import NormalizedChannel, NormalizedVideo


class AnalyzeRequest(BaseModel):
    youtube_url: str


class MLStatus(BaseModel):
    available: bool = False
    message: str = "ML prediction pipeline will be connected later"


class AnalysisReport(BaseModel):
    analysis_id: uuid.UUID
    status: str
    cached: bool = False
    created_at: datetime | None = None
    video: NormalizedVideo
    channel: NormalizedChannel | None = None
    features: FeaturePayload
    feature_readiness: dict[str, FeatureStatus]
    ml_status: MLStatus = MLStatus()
    source: str = "youtube_data_api"
    raw_api_response: dict | None = None


class AnalysisSummary(BaseModel):
    analysis_id: uuid.UUID
    video_id: str
    title: str
    channel_title: str | None = None
    thumbnail_url: str | None = None
    created_at: datetime | None = None
